from abc import ABCMeta, abstractmethod
from typing import Tuple, Union
import os, re

from emitter import Emitter

_operators: "dict[str, Tuple[int, bool, str]]" = {
	"+": (0, False, "__ADD_TYPE1_TYPE2", 2),
	"-": (0, False, "__SUB_TYPE1_TYPE2", 2),
	"*": (0, False, "__MUL_TYPE1_TYPE2", 2),
	"/": (0, False, "__DIV_TYPE1_TYPE2", 2),
	"<<": (0, False, "__LSHIFT_TYPE1_TYPE2", 2),
	">>": (0, False, "__RSHIFT_TYPE1_TYPE2", 2),
	"AND": (0, False, "__AND_TYPE1_TYPE2", 2),
	"OR": (0, False, "__OR_TYPE1_TYPE2", 2),
	"XOR": (0, False, "__XOR_TYPE1_TYPE2", 2)
}

class Type(metaclass=ABCMeta):
	def __init__(self, name: str): self._name = name
	def GetName(self) -> str: return self._name
	@abstractmethod
	def GetSize(self) -> int: ...
	@abstractmethod
	def Resolve(self, resolver) -> None: ...

class Resolver:
	def __init__(self, types: "list[Type]", functions: "list[Callable]"):
		self._types = types
		self._functions: "dict[str, Callable]" = {}
		for func in functions: self._functions[func.GetName()] = func

	def ResolveSelf(self):
		for type in self._types: type.Resolve(self)

	def Resolve(self, value: Union[Type, str]) -> Type:
		if isinstance(value, Type):
			for otherType in self._types:
				if otherType.GetName() == value.GetName():
					return value
			self._types.append(value)
			return value
		else: return self.GetType(value)
	
	def DefineFunction(self, func):
		f: Callable = func
		self._functions[f.GetName()] = f

	def GetFunction(self, name: str):
		if name in self._functions: return self._functions[name]
		else: raise Exception("Undefined function \"" + name + "\".")

	def GetType(self, name: str) -> Type:
		if name.endswith("*"):
			return PointerType(self.GetType(name[:len(name) - 1]))
		else:
			for type in self._types:
				if type.GetName() == name: return type
			raise Exception("Undefined type \"" + name + "\".")

class MemoryBlock(metaclass=ABCMeta):
	@abstractmethod
	def CanRead(self) -> bool: ...
	@abstractmethod
	def CanWrite(self) -> bool: ...
	@abstractmethod
	def GetSize(self) -> int: ...
	@abstractmethod
	def GetSubBlocks(self) -> "list[Tuple[str, MemoryBlock]]": ...
	@abstractmethod
	def EmitLoadAddress(self, emitter: Emitter, context): ...
	@abstractmethod
	def EmitLoad(self, emitter: Emitter, context): ...
	@abstractmethod
	def EmitStore(self, emitter: Emitter, context): ...

class Variable(MemoryBlock):
	@abstractmethod
	def GetType(self) -> Union[Type, str]: ...
	@abstractmethod
	def GetName(self) -> str: ...
	def IsByReference(self) -> bool: return False
	@abstractmethod
	def Resolve(self, resolver: Resolver, context) -> None: ...

	def GetSize(self) -> int:
		type = self.GetType()
		if isinstance(type, str): raise TypeError("Variable must be resolved before collecting sub-blocks.")
		else: return type.GetSize()

	def GetSubBlocks(self) -> "list[Tuple[str, MemoryBlock]]":
		type = self.GetType()
		if isinstance(type, str): raise TypeError("Variable must be resolved before collecting sub-blocks.")
		elif isinstance(type, ComplexType): return [(field.GetName(), field) for field in type.GetFields()]
		else: return []
	
	def GetVariable(self, name: str):
		type = self.GetType()
		if self.IsByReference() and isinstance(type, PointerType): type = type.GetReferencedType()
		if name == None: return self
		elif isinstance(type, str): raise Exception("Type is not resolved.")
		elif isinstance(type, ComplexType):
			path = name.split(".")

			for i in range(len(type.GetFields())):
				field = type.GetField(i, self)
				if field != None and field.GetName() == path[0]:
					if len(path) == 1: return field
					else: return field.GetVariable(".".join(path[1:]))

		raise Exception("Undefined variable \"" + name + "\".")

class Field(Variable):
	def __init__(self, relativeTo: Variable, type: Union[Type, str], name: str, index: int, offset: int = 0):
		self._relativeTo = relativeTo
		self._offset = offset
		self._type = type
		self._name = name
		self._index = index
	
	def CanRead(self) -> bool: return self._relativeTo.CanRead()
	def CanWrite(self) -> bool: return self._relativeTo.CanWrite()
	def GetType(self) -> Union[Type, str]: return self._type
	def GetName(self) -> str: return self._name
	def GetIndex(self) -> int: return self._index
	def Resolve(self, resolver: Resolver, context) -> None: self._type = resolver.Resolve(self._type)

	def EmitLoadAddress(self, emitter: Emitter, context):
		self._relativeTo.EmitLoadAddress(emitter, context)
		emitter.push(self._offset)
		emitter.add()

	def EmitLoad(self, emitter: Emitter, context):
		self.EmitLoadAddress(emitter, context)
		emitter.ld_ptr(self.GetSize())

	def EmitStore(self, emitter: Emitter, context):
		self.EmitLoadAddress(emitter, context)
		emitter.st_ptr(self.GetSize())

class Parameter(Variable):
	def __init__(self, type: Union[Type, str], isByReference: bool, name: str, index: int):
		self._type = type
		self._resolved = None
		self._name = name
		self._index = index
		self._ref = isByReference

	def CanRead(self) -> bool: return True
	def CanWrite(self) -> bool: return True
	def GetType(self) -> Union[Type, str]: return self._type if self._resolved == None else self._resolved
	def GetName(self) -> str: return self._name
	def GetIndex(self) -> int: return self._index
	def IsByReference(self) -> bool: return self._ref
	def Resolve(self, resolver: Resolver) -> None:
		self._resolved = resolver.Resolve(self._type)
		if self._ref: self._resolved = PointerType(self._resolved)

	def EmitLoadAddress(self, emitter: Emitter, context):
		offset = 2
		for i in range(context.GetArgumentCount() - 1, self.GetIndex(), -1):
			offset += context.GetArgument(i).GetType().GetSize()
		emitter.ld_bp()
		emitter.push(offset)
		emitter.add()
		if self._ref: emitter.ld_ptr(self.GetSize())

	def EmitLoad(self, emitter: Emitter, context) -> None:
		self.EmitLoadAddress(emitter, context)
		emitter.ld_ptr(self.GetSize())

	def EmitStore(self, emitter: Emitter, context) -> None:
		self.EmitLoadAddress(emitter, context)
		emitter.st_ptr(self.GetSize())

class Local(Variable):
	def __init__(self, type: Union[Type, str], name: str, initial: Union[int, None]):
		self._type = type
		self._name = name
		self._initial = initial
	
	def CanRead(self) -> bool: return True
	def CanWrite(self) -> bool: return True
	def GetType(self) -> Union[Type, str]: return self._type
	def GetName(self) -> str: return self._name
	def GetInitialValue(self) -> Union[int, None]: return self._initial
	def Resolve(self, resolver: Resolver) -> None: self._type = resolver.Resolve(self._type)

	def EmitLoadAddress(self, emitter: Emitter, context):
		offset = 0
		for i in range(context.GetLocalCount()):
			local: Local = context.GetLocal(i)
			offset += local.GetType().GetSize()
			if local == self: break
		emitter.ld_bp()
		emitter.push(offset)
		emitter.sub()

	def EmitLoad(self, emitter: Emitter, context):
		self.EmitLoadAddress(emitter, context)
		emitter.ld_ptr(self.GetSize())

	def EmitStore(self, emitter: Emitter, context):
		self.EmitLoadAddress(emitter, context)
		emitter.st_ptr(self.GetSize())

class ReturnVariable(Variable):
	def __init__(self, type: Union[Type, str]):
		self._type = type
	
	def CanRead(self) -> bool: return True
	def CanWrite(self) -> bool: return True
	def GetType(self) -> Union[Type, str]: return self._type
	def SetType(self, type: Union[Type, str]): self._type = type
	def GetName(self) -> str: return ""
	def Resolve(self, resolver: Resolver) -> None: self._type = resolver.Resolve(self._type)

	def EmitLoadAddress(self, emitter: Emitter, context):
		offset = 2
		for i in range(context.GetArgumentCount()):
			offset += context.GetArgument(i).GetType().GetSize()
		emitter.ld_bp()
		emitter.push(offset)
		emitter.add()

	def EmitLoad(self, emitter: Emitter, context):
		if self.GetType().GetSize() > 0:
			self.EmitLoadAddress(emitter, context)
			emitter.ld_ptr(self.GetSize())

	def EmitStore(self, emitter: Emitter, context):
		if self.GetType().GetSize() > 0:
			self.EmitLoadAddress(emitter, context)
			emitter.st_ptr(self.GetSize())

class EmptyType(Type):
	def __init__(self, name: str): super().__init__(name)
	def GetSize(self) -> int: return 0
	def Resolve(self, resolver) -> None: return

VoidType = EmptyType("Void")

class PrimitiveType(Type):
	def __init__(self, name: str): super().__init__(name)
	@abstractmethod
	def IsSigned(self) -> bool: ...
	def GetSize(self) -> int: return 1
	def Resolve(self, resolver) -> None: return

class PointerType(PrimitiveType):
	def __init__(self, referenced: Union[Type, str]): self._referenced = referenced
	def GetName(self) -> str:
		if isinstance(self._referenced, Type):
			return self._referenced.GetName() + "*"
		else:
			return self._referenced + "*"
	def IsSigned(self) -> bool: return False
	def GetReferencedType(self) -> Union[Type, str]: return self._referenced
	def Resolve(self, resolver: Resolver) -> None: self._referenced = resolver.Resolve(self._referenced)
	def __eq__(self, __o: object) -> bool:
		return isinstance(__o, PointerType) and self.GetReferencedType() == __o.GetReferencedType()
	def __ne__(self, __o: object) -> bool:
		return not (self == __o)

class SignedInteger(PrimitiveType):
	def __init__(self): super().__init__("Integer")
	def IsSigned(self) -> bool: return True
	def __eq__(self, __o: object) -> bool:
		return isinstance(__o, SignedInteger)
	def __ne__(self, __o: object) -> bool:
		return not (self == __o)

class UnsignedInteger(PrimitiveType):
	def __init__(self): super().__init__("UInteger")
	def IsSigned(self) -> bool: return False
	def __eq__(self, __o: object) -> bool:
		return isinstance(__o, UnsignedInteger)
	def __ne__(self, __o: object) -> bool:
		return not (self == __o)

class ComplexType(Type):
	def __init__(self, name: str, fields: "list[Field]"):
		super().__init__(name)
		self._fields = fields
	def GetSize(self) -> int: return sum([field.GetType().GetSize() for field in self._fields])
	def GetFields(self) -> "list[Field]": return self._fields
	
	def GetField(self, nameOrIndex: Union[str, int], relativeTo: Union[Variable, None] = None) -> Union[Field, None]:
		if isinstance(nameOrIndex, int):
			offset = 0
			for i in range(nameOrIndex): offset += self._fields[i].GetSize()
			field = self._fields[nameOrIndex]
			return Field(relativeTo, field.GetType(), field.GetName(), field.GetIndex(), offset)
		elif isinstance(nameOrIndex, str):
			offset = 0
			for field in self._fields:
				if field.GetName() == nameOrIndex:
					return Field(relativeTo, field.GetType(), field.GetName(), field.GetIndex(), offset)
				else:
					offset += field.GetSize()
		return None
	
	def GetFieldOffset(self, name: str) -> Union[int, None]:
		offset = 0
		for field in self._fields:
			if field.GetName() == name: return offset
			else: offset += field.GetType().GetSize()
		return None
	
	def Resolve(self, resolver: Resolver) -> None:
		for field in self._fields: field.Resolve(resolver, self)

class Expression(metaclass=ABCMeta):
	@abstractmethod
	def Resolve(self, resolver: Resolver, context) -> None: ...
	@abstractmethod
	def GetResultType(self) -> Type: ...
	@abstractmethod
	def Emit(self, emitter: Emitter, context) -> None: ...

class VoidExpression(Expression):
	def Resolve(self, resolver: Resolver, context): return
	def GetResultType(self) -> Type: return VoidType
	def Emit(self, emitter: Emitter, context): return

class ConstantExpression(Expression):
	def __init__(self, value: int, type: Union[Type, str]):
		self._value = value
		self._type = type

	def Resolve(self, resolver: Resolver, context): self._type = resolver.Resolve(self._type)
	def GetResultType(self) -> Type: return self._type

	def Emit(self, emitter: Emitter, context):
		emitter.push(self._value)

class VariableExpression(Expression):
	def __init__(self, target: str):
		self._target = target
	
	def GetName(self) -> str:
		return self._target.GetName() if isinstance(self._target, Variable) else self._target

	def GetVariable(self) -> Variable:
		if isinstance(self._target, Variable): return self._target
		else: raise Expression("Type is not resolved.")

	def Resolve(self, resolver: Resolver, context):
		if not isinstance(self._target, Variable): self._target = context.GetVariable(self._target)
	
	def GetResultType(self) -> Type:
		if isinstance(self._target, Variable): return self._target.GetType()
		else: raise Exception("Type is not resolved.")

	def Emit(self, emitter: Emitter, context):
		if isinstance(self._target, Variable): return self._target.EmitLoad(emitter, context)
		else: raise Exception("Type is not resolved.")

class UnaryOperandExpression(Expression):
	def __init__(self, operator: str, expr: Expression):
		self._operator = operator
		self._expr = expr
		self._call = None

	def Resolve(self, resolver: Resolver, context):
		self._expr.Resolve(resolver, context)
		self._call = CallExpression(self.GetOperationName(), [self._expr])
		self._call.Resolve(resolver, context)

	def GetOperationName(self) -> str:
		type = self._expr.GetResultType()
		return _operators[self._operator][2].replace("TYPE1", type.GetName())

	def GetResultType(self) -> Type:
		if self._call == None: raise Exception("Expression has not been resolved.")
		return self._call.GetResultType()

	def Emit(self, emitter: Emitter, context):
		if self._call == None: raise Exception("Expression has not been resolved.")
		self._call.Emit(emitter, context)

class BinaryOperandExpression(Expression):
	def __init__(self, operator: str, exprA: Expression, exprB: Expression):
		self._operator = operator
		self._exprA = exprA
		self._exprB = exprB
		self._call = None

	def Resolve(self, resolver: Resolver, context):
		self._exprA.Resolve(resolver, context)
		self._exprB.Resolve(resolver, context)
		self._call = CallExpression(self.GetOperationName(), [self._exprA, self._exprB])
		self._call.Resolve(resolver, context)
	
	def GetOperationName(self) -> str:
		a = self._exprA.GetResultType()
		b = self._exprB.GetResultType()
		return _operators[self._operator][2].replace("TYPE1", a.GetName()).replace("TYPE2", b.GetName())

	def GetResultType(self) -> Type:
		if self._call == None: raise Exception("Expression has not been resolved.")
		return self._call.GetResultType()

	def Emit(self, emitter: Emitter, context):
		if self._call == None: raise Exception("Expression has not been resolved.")
		self._call.Emit(emitter, context)

class CastExpression(Expression):
	def __init__(self, type: Union[Type, str], expr: Expression):
		self._type = type
		self._expr = expr
		self._call = None

	def Resolve(self, resolver: Resolver, context):
		self._type = resolver.Resolve(self._type)
		self._expr.Resolve(resolver, context)
		self._call = CallExpression(self.GetOperationName(), [self._expr])
		self._call.Resolve(resolver, context)

	def GetOperationName(self) -> str:
		return f"__CAST_{self._expr.GetResultType().GetName()}_{self._type.GetName()}"

	def GetResultType(self) -> Type:
		if self._call == None: raise Exception("Expression has not been resolved.")
		return self._call.GetResultType()

	def Emit(self, emitter: Emitter, context):
		if self._call == None: raise Exception("Expression has not been resolved.")
		self._call.Emit(emitter, context)

class CallExpression(Expression):
	def __init__(self, target: "Union[Callable, str]", args: "list[Expression]"):
		self._target = target
		self._addressOf = isinstance(target, str) and target.upper() == "ADDRESSOF"
		self._args = args

	def Resolve(self, resolver: Resolver, context):
		for arg in self._args: arg.Resolve(resolver, context)
		if not (isinstance(self._target, Callable) or self._addressOf):
			self._target = resolver.GetFunction(self._target)
	
	def GetResultType(self) -> Type:
		if self._addressOf: return self.GetAddressOfType()
		elif isinstance(self._target, Callable): return self._target.GetReturnType()
		else: raise Exception("Function is not resolved.")
	
	def GetAddressOfType(self) -> Type:
		if len(self._args) == 0: return PointerType(VoidType)
		else: return PointerType(self._args[0].GetResultType())

	def Emit(self, emitter: Emitter, context):
		if self._addressOf:
			if len(self._args) != 1: raise Exception("Expected 1 operand for \"ADDRESSOF\" operator.")
			expr = self._args[0]
			if not isinstance(expr, VariableExpression):
				raise Exception("Expression does not have an address.")
			expr.GetVariable().EmitLoadAddress(emitter, context)
		else:
			if not isinstance(self._target, Callable): raise Exception("Function is not resolved.")
			if self._target.IsInline():
				for arg in self._args: arg.Emit(emitter, context)
				self._target.Emit(emitter)
			else:
				if self._target.GetReturnType().GetSize() > 0:
					emitter.add_sp(self._target.GetReturnType().GetSize())
				size = 0
				for arg in self._args:
					arg.Emit(emitter, context)
					size += arg.GetResultType().GetSize()
				emitter.call(self._target.GetName())
				if size > 0: emitter.rem_sp(size)

class Statement(metaclass=ABCMeta):
	@abstractmethod
	def GetLocals(self) -> "list[Local]": ...
	@abstractmethod
	def Resolve(self, resolver: Resolver, context) -> None: ...
	@abstractmethod
	def Emit(self, emitter: Emitter, context) -> None: ...

class LocalStatement(Statement):
	def __init__(self, local: Local):
		self._local = local

	def GetLocals(self) -> "list[Local]": return [self._local]
	def Resolve(self, resolver: Resolver, context): self._local.Resolve(resolver)
	def Emit(self, emitter: Emitter, context): return

class AssignmentStatement(Statement):
	def __init__(self, target: Union[Variable, str], expr: Expression):
		self._target = target
		self._expr = expr

	def GetLocals(self) -> "list[Local]": return []
	def Resolve(self, resolver: Resolver, context): self._expr.Resolve(resolver, context)

	def Emit(self, emitter: Emitter, context):
		self._expr.Emit(emitter, context)
		if isinstance(self._target, Variable): self._target.EmitStore(context)
		else: context.GetVariable(self._target).EmitStore(emitter, context)

class ReturnStatement(Statement):
	def __init__(self, expr: Expression):
		self._expr = expr
	
	def GetLocals(self) -> "list[Local]": return []
	def Resolve(self, resolver: Resolver, context): self._expr.Resolve(resolver, context)
	
	def Emit(self, emitter: Emitter, context):
		if self._expr.GetResultType() != context.GetReturnType():
			raise Exception("Return value does not match function return type.")
		self._expr.Emit(emitter, context)
		ReturnVariable(self._expr.GetResultType()).EmitStore(emitter, context)
		emitter.jmp(f"__{context.GetName()}__return")

class AssemblyLoadStatement(Statement):
	def __init__(self, source: Union[Variable, str]):
		self._source = source
	
	def GetLocals(self) -> "list[Local]": return []
	def Resolve(self, resolver: Resolver, context): return

	def Emit(self, emitter: Emitter, context):
		if isinstance(self._source, Variable): self._source.EmitLoad(emitter, context)
		else: context.GetVariable(self._source).EmitLoad(emitter, context)

class AssemblyStoreStatement(Statement):
	def __init__(self, source: Union[Variable, str]):
		self._source = source
	
	def GetLocals(self) -> "list[Local]": return []
	def Resolve(self, resolver: Resolver, context): return

	def Emit(self, emitter: Emitter, context):
		if isinstance(self._source, Variable): self._source.EmitStore(emitter, context)
		else: context.GetVariable(self._source).EmitStore(emitter, context)

class AssemblyInstructionStatement(Statement):
	def __init__(self, operation: str, operands: "list[str]"):
		self._operation = operation
		self._operands = operands
	
	def GetLocals(self) -> "list[Local]": return []
	def Resolve(self, resolver: Resolver, context): return
	def Emit(self, emitter: Emitter, context): emitter.emit_raw(self._operation, self._operands)

class CallStatement(Statement):
	def __init__(self, expr: CallExpression):
		self._expr = expr

	def GetLocals(self) -> "list[Local]": return []
	def Resolve(self, resolver: Resolver, context): self._expr.Resolve(resolver, context)

	def Emit(self, emitter: Emitter, context):
		self._expr.Emit(emitter, context)
		if self._expr.GetResultType().GetSize() > 0:
			emitter.rem_sp(self._expr.GetResultType().GetSize())

class Callable(metaclass=ABCMeta):
	def __init__(self, name: str):
		self._name = name
	
	def GetName(self) -> str: return self._name
	def IsInline(self) -> bool: return False
	@abstractmethod
	def GetArgumentsSize(self) -> int: ...
	@abstractmethod
	def GetArgumentCount(self) -> int: ...
	@abstractmethod
	def GetArgument(self, index: int) -> Parameter: ...
	@abstractmethod
	def GetLocalsSize(self) -> int: ...
	@abstractmethod
	def GetLocalCount(self) -> int: ...
	@abstractmethod
	def GetLocal(self, index: int) -> Local: ...
	@abstractmethod
	def GetReturnType(self) -> Type: ...
	@abstractmethod
	def GetBody(self) -> "list[Statement]": ...
	@abstractmethod
	def Resolve(self, resolver: Resolver) -> None: ...

	def GetVariable(self, name: str) -> Variable:
		parts = name.split(".")

		for i in range(self.GetLocalCount()):
			if self.GetLocal(i).GetName() == parts[0]:
				if len(parts) == 1: return self.GetLocal(i)
				else: return self.GetLocal(i).GetVariable(".".join(parts[1:]))
		
		for i in range(self.GetArgumentCount()):
			if self.GetArgument(i).GetName() == parts[0]:
				if len(parts) == 1: return self.GetArgument(i)
				else: return self.GetArgument(i).GetVariable(".".join(parts[1:]))

	def Emit(self, emitter: Emitter):
		label = emitter.create_label(self.GetName())
		emitter.mark_label(label)
		emitter.ld_bp()
		emitter.ld_sp()
		emitter.st_bp()
		for i in range(self.GetLocalCount()):
			local = self.GetLocal(i)
			value = local.GetInitialValue()
			if value == None: emitter.add_sp(local.GetType().GetSize())
			else:
				for _ in local.GetType().GetSize(): emitter.push(value)
		for statement in self.GetBody(): statement.Emit(emitter, self)
		emitter.mark_label(emitter.create_label(f"__{self.GetName()}__return"))
		emitter.ld_bp()
		emitter.st_sp()
		emitter.st_bp()
		emitter.ret()

class InlineBody(Callable):
	def __init__(self, name: str, returnType: "Union[Type, str]", body: "list[Statement]"):
		super().__init__(name)
		self._returnType = returnType
		self._body = body
	
	def IsInline(self) -> bool: return True
	def GetArgumentsSize(self) -> int: return 0
	def GetArgumentCount(self) -> int: return 0
	def GetArgument(self, index: int) -> Parameter: raise IndexError()
	def GetLocalsSize(self) -> int: return 0
	def GetLocalCount(self) -> int: return 0
	def GetLocal(self, index: int) -> Local: raise IndexError()
	def GetReturnType(self) -> Type:
		if isinstance(self._returnType, Type): return self._returnType
		else: raise Exception("Type is not resolved.")
	def GetBody(self) -> "list[Statement]": return self._body

	def Resolve(self, resolver: Resolver) -> None:
		self._returnType = resolver.Resolve(self._returnType)
		for statement in self.GetBody(): statement.Resolve(resolver, self)
	
	def Emit(self, emitter: Emitter):
		for statement in self.GetBody(): statement.Emit(emitter, self)

class SubRoutine(Callable):
	def __init__(self, name: str, args: "list[Tuple[Union[Type, str], str, bool]]", body: "list[Statement]"):
		super().__init__(name)
		self._namedArgs: "list[Parameter]" = []
		i = 0
		for type, name, ref in args:
			self._namedArgs.append(Parameter(type, ref, name, i))
			i += 1
		self._body = body
	
	def GetArgumentsSize(self) -> int: return sum([param.GetType().GetSize() for param in self._namedArgs])
	def GetArgumentCount(self) -> int: return len(self._namedArgs)
	def GetArgument(self, index: int) -> Parameter: return self._namedArgs[index]
	def GetLocalsSize(self) -> int:
		result = 0
		for statement in self._body:
			for local in statement.GetLocals():
				result += local.GetType().GetSize()
		return result
	def GetLocalCount(self) -> int: return sum([len(statement.GetLocals()) for statement in self._body])
	def GetLocal(self, index: int) -> Local:
		offset = index
		for statement in self._body:
			for local in statement.GetLocals():
				if offset == 0: return local
				offset -= 1
		raise IndexError()
	def GetReturnType(self) -> Type: return VoidType
	def GetBody(self) -> "list[Statement]": return self._body
	
	def Resolve(self, resolver: Resolver) -> None:
		for arg in self._namedArgs: arg.Resolve(resolver)
		for statement in self.GetBody(): statement.Resolve(resolver, self)

class Function(Callable):
	def __init__(self, name: str, args: "list[Tuple[Union[Type, str], str]]", returnType: "Union[Type, str]", body: "list[Statement]"):
		super().__init__(name)
		self._namedArgs: "list[Parameter]" = []
		i = 0
		for type, name, ref in args:
			self._namedArgs.append(Parameter(type, ref, name, i))
			i += 1
		self._returnType = returnType
		self._body = body
	
	def GetArgumentsSize(self) -> int: return sum([param.GetType().GetSize() for param in self._namedArgs])
	def GetArgumentCount(self) -> int: return len(self._namedArgs)
	def GetArgument(self, index: int) -> Parameter: return self._namedArgs[index]
	def GetLocalsSize(self) -> int:
		result = 0
		for statement in self._body:
			for local in statement.GetLocals():
				result += local.GetType().GetSize()
		return result
	def GetLocalCount(self) -> int: return sum([len(statement.GetLocals()) for statement in self._body])
	def GetLocal(self, index: int) -> Local:
		offset = index
		for statement in self._body:
			for local in statement.GetLocals():
				if offset == 0: return local
				offset -= 1
		raise IndexError()
	def GetReturnType(self) -> Type:
		if isinstance(self._returnType, Type): return self._returnType
		else: raise Exception("Type is not resolved.")
	def GetBody(self) -> "list[Statement]": return self._body
	
	def Resolve(self, resolver: Resolver) -> None:
		self._returnType = resolver.Resolve(self._returnType)
		for arg in self._namedArgs: arg.Resolve(resolver)
		for statement in self.GetBody(): statement.Resolve(resolver, self)

class Module:
	def __init__(self, name: str, types: "list[Type]", code: "list[Callable]"):
		self._name = name
		self._types = types
		self._code = code
	
	def GetName(self) -> str: return self._name
	def GetTypes(self) -> "list[Type]": return self._types
	def GetCode(self) -> "list[Callable]": return self._code

	def GetResolver(self, additionalTypes: "list[Type]" = [], additionalFunctions: "list[Callable]" = []) -> Resolver:
		return Resolver(self.GetTypes() + additionalTypes, self.GetCode() + additionalFunctions)

	def Resolve(self, resolver: Resolver):
		for type in self._types: type.Resolve(resolver)
		for code in self._code: code.Resolve(resolver)

	def Emit(self, emitter: Emitter):
		for code in self._code: code.Emit(emitter)

_statements = {}
_blocks = {}

def parse_value(text: str) -> int:
	match = re.match(r"^\-?((0X[0-9A-F]+)|(0O[0-7]+)|(0B[01]+)|([1-9][0-9]+)|([0-9]))$", text.upper())
	negate = False
	result = 0
	if match == None: raise Exception("Invalid value.")
	if text.startswith("-"):
		negate = True
		text = text[1:]
	if text.startswith("0X"): result = int(text[2:], base=16)
	elif text.startswith("0O"): result = int(text[2:], base=8)
	elif text.startswith("0B"): result = int(text[2:], base=2)
	else: result = int(text)
	return -result if negate else result

def parse_local(line: str) -> Local:
	match = re.match(r"^[Dd][Ii][Mm]\s+(\w[\w\d]*)\s+[Aa][Ss]\s+(\w[\w\d]*)\s*(=\s*(.+))?$", line.strip())
	if match == None: raise Exception("Invalid local declaration. Example: Dim value As Integer = 10")
	name = match.group(1)
	type = match.group(2)
	initial = match.group(4)
	if initial != None: initial = parse_value(initial.strip())
	return Local(type, name, initial)

def parse_local_statement(line: str) -> LocalStatement:
	return LocalStatement(parse_local(line))

def parse_field(line: str, index: int) -> Field:
	match = re.match(r"^DIM\s+(\w[\w\d]*)\s+AS\s+(\w[\w\d]*)$", line.strip(), re.IGNORECASE)
	if match == None: raise Exception("Invalid field declaration. Example: Dim value As Integer")
	name = match.group(1)
	type = match.group(2)
	return Field(None, type, name, index)

def parse_struct(lines: "list[str]") -> ComplexType:
	if len(lines) < 2: raise Exception("Invalid structure.")
	header = re.match(r"^STRUCTURE\s+(\w[\w\d]*)$", lines[0].strip(), re.IGNORECASE)
	footer = re.match(r"^END\s+STRUCTURE$", lines[len(lines) - 1].strip(), re.IGNORECASE)
	if header == None: raise Exception("Invalid structure header. Example: Structure MyData")
	if footer == None: raise Exception("Invalid structure footer. Example: End Structure")
	offset = -1
	fields = []
	for i in range(1, len(lines) - 1):
		if len(lines[i].strip()) > 0:
			fields.append(parse_field(lines[i], i + offset))
		else:
			offset -= 1
	return ComplexType(header.group(1), fields)

def parse_arguments(argList: str) -> "list[Tuple[Union[Type, str], str, bool]]":
	result = []
	if len(argList.strip()) == 0: return result
	for arg in [arg.strip() for arg in argList.split(",")]:
		match = re.match(r"^(?:(BYREF)\s+)?(\w[\w\d]*)\s+AS\s+(\w[\w\d\*]*)$", arg, re.IGNORECASE)
		if match == None: raise Exception("Invalid argument. Example: value As Integer")
		result.append((match.group(3), match.group(2), str(match.group(1)).upper() == "BYREF"))
	return result

def parse_subroutine(lines: "list[Union[str, list]]") -> SubRoutine:
	if len(lines) < 2: raise Exception("Invalid subroutine.")
	header = re.match(r"^SUB\s+(\w[\w\d]*)\s*\((\s*(?:(?:\s*(?:BYREF\s+)?\w[\w\d]*\s+AS\s+\w[\w\d\*]*\s*,)*\s*(?:BYREF\s+)?\w[\w\d]*\s+AS\s+\w[\w\d\*]*\s*)?)\)$", lines[0].strip(), re.IGNORECASE)
	footer = re.match(r"^END\s+SUB$", lines[len(lines) - 1].strip(), re.IGNORECASE)
	if header == None: raise Exception("Invalid subroutine header. Example: Sub MyCode(a As Integer, b As Integer)")
	if footer == None: raise Exception("Invalid subroutine footer. Example: End Sub")
	statements = []
	for i in range(1, len(lines) - 1):
		statement = parse_statement(lines[i])
		if statement != None: statements.append(statement)
	return SubRoutine(header.group(1), parse_arguments(header.group(2)), statements)

def parse_function(lines: "list[Union[str, list]]") -> Function:
	if len(lines) < 2: raise Exception("Invalid function.")
	header = re.match(r"^FUNCTION\s+(\w[\w\d]*)\s*\((\s*(?:(?:\s*(?:BYREF\s+)?\w[\w\d]*\s+AS\s+\w[\w\d\*]*\s*,)*\s*(?:BYREF\s+)?\w[\w\d]*\s+AS\s+\w[\w\d\*]*\s*)?)\)\s+AS\s+(\w[\w\d\*]*)$", lines[0].strip(), re.IGNORECASE)
	footer = re.match(r"^END\s+FUNCTION$", lines[len(lines) - 1].strip(), re.IGNORECASE)
	if header == None: raise Exception("Invalid function header. Example: Function MyCode(a As Integer, b As Integer) As Integer")
	if footer == None: raise Exception("Invalid function footer. Example: End Function")
	statements = []
	for i in range(1, len(lines) - 1):
		statement = parse_statement(lines[i])
		if statement != None: statements.append(statement)
	return Function(header.group(1), parse_arguments(header.group(2)), header.group(3), statements)

def collect_blocks(lines: "list[str]", isRootBlock=False) -> "Tuple[list[Union[str, list]], int]":
	result = []
	i = 0
	blockName = ""
	while i < len(lines):
		innerBlock = False
		if i == 0 and not isRootBlock:
			header = re.match(r"^(\w+)", lines[0].strip())
			if header == None: raise Exception("Invalid block header.")
			blockName = header.group(1).upper()
		else:
			for key in _blocks:
				if lines[i].upper().strip().startswith(key):
					block, length = collect_blocks(lines[i:])
					result.append(block)
					i += length
					innerBlock = True
					break
		if not innerBlock:
			line = lines[i]
			result.append(line)
			i += 1
			if not isRootBlock:
				footer = re.search("^END\\s+" + blockName + "$", line.strip(), re.IGNORECASE)
				if footer != None: return result, i
	if isRootBlock:
		return result, i
	else:
		raise Exception("\"" + blockName + "\" block is missing \"END " + blockName + "\"")

def parse_expression(line: str) -> Expression:
	tokens = re.findall(r"(?:\w[\w\d\.\*]*\(?)|(?:\-?\d[\w\d\.]*)|(?:\s+)|(?:[\+\-\*\/\.]+|(?:AS))|(?:\()|(?:\))", line, re.IGNORECASE)
	queue = []
	stack = []

	def isOperator(name: str) -> bool: return (name.upper() == "AS") or (name.upper() in _operators)
	def getPrecedence(name: str) -> int: return _operators[name][0]
	def isLeftAssociative(name: str) -> bool: return _operators[name][1]

	for token in tokens:
		if token.isspace(): continue
		if isOperator(token):
			while (len(stack) > 0) and (stack[len(stack) - 1] != "(") and ((getPrecedence(stack[len(stack) - 1]) > getPrecedence(token)) or (isLeftAssociative(token) and getPrecedence(stack[len(stack) - 1]) == getPrecedence(token))):
				queue.append(stack.pop())
			stack.append(token)
		elif len(token) > 1 and token.endswith("("):
			stack.append(token)
			stack.append("(")
			queue.append(")")
		elif token == "(":
			stack.append("(")
		elif token == ")":
			if len(stack) == 0: raise Exception("Missing \"(\".")
			while stack[len(stack) - 1] != "(":
				if len(stack) == 0: raise Exception("Missing \"(\".")
				queue.append(stack.pop())
			stack.pop()
			if len(stack) > 0:
				top = stack[len(stack) - 1]
				if len(top) > 0 and top.endswith("("):
					queue.append(stack.pop())
		else:
			queue.append(token)

	while len(stack) > 0:
		token = stack.pop()
		if token == "(": raise Exception("Missing \")\".")
		queue.append(token)
	
	for token in queue:
		if token == ")":
			stack.append(token)
		elif isOperator(token):
			if token.upper() == "AS":
				if len(stack) < 1: raise Exception("Expected 2 operands for \"" + token + "\" operator.")
				type = stack.pop()
				expr = stack.pop()
				if not isinstance(type, VariableExpression): raise Exception("Expected type name for second operand of \"AS\".")
				stack.append(CastExpression(type.GetName(), expr))
			else:
				argCount = _operators[token][3]
				if argCount == 1:
					if len(stack) < 1: raise Exception("Expected 1 operand for \"" + token + "\" operator.")
					stack.append(UnaryOperandExpression(token, stack.pop()))
				elif argCount == 2:
					if len(stack) < 2: raise Exception("Expected 2 operands for \"" + token + "\" operator.")
					argB = stack.pop()
					argA = stack.pop()
					stack.append(BinaryOperandExpression(token, argA, argB))
		elif token.endswith("(") and len(token) > 1:
			args = []
			if len(stack) == 0: raise Exception("Invalid call expression.")
			while stack[len(stack) - 1] != ")":
				args.append(stack.pop())
				if len(stack) == 0: raise Exception("Missing argument list terminator.")
			stack.pop()
			args.reverse()
			stack.append(CallExpression(token[:len(token) - 1], args))
		else:
			try:
				stack.append(ConstantExpression(parse_value(token), "Integer"))
			except:
				stack.append(VariableExpression(token))
	
	if len(stack) != 1: raise Exception("Expressions must produce one value.")
	return stack[0]

def parse_asm_statement(line: str) -> Statement:
	match = re.match(r"^\s*ASM\s+(\w+)\s+([\w\d\.]+)(?:\s+(.*)\s*)?", line, re.IGNORECASE)
	if match == None: raise Exception("Invalid assembly statement.")
	if match.group(1).upper() == "LOAD":
		if match.group(3) == "": return AssemblyLoadStatement(match.group(2))
		else: raise Exception("Assembly load statement only accepts 1 parameter.")
	elif match.group(1).upper() == "SAVE":
		if match.group(3) == "": return AssemblyStoreStatement(match.group(2))
		else: raise Exception("Assembly save statement only accepts 1 parameter.")
	elif match.group(1).upper() == "EXEC":
		if match.group(3) == "": return AssemblyInstructionStatement(match.group(2), [])
		else: return AssemblyInstructionStatement(match.group(2), re.split("\s+", match.group(3)))
	else:
		raise Exception("Unrecognized assembly statement type.")

def parse_return_statement(line: str) -> ReturnStatement:
	match = re.match(r"^\s*RETURN(?:\s+(.*))?\s*$", line, re.IGNORECASE)
	if match == None: raise Exception("Invalid return statement.")
	expression = match.group(1)
	if expression == "": return ReturnStatement(VoidExpression())
	else: return ReturnStatement(parse_expression(expression))

def parse_assign_statement(line: str) -> AssignmentStatement:
	match = re.match(r"^\s*(\w[\w\d\.]*)\s*=\s*(.*)", line)
	if match == None: raise Exception("Invalid assignment statement.")
	target = match.group(1)
	expression = match.group(2)
	return AssignmentStatement(target, parse_expression(expression))

def parse_call_statement(line: str) -> CallStatement:
	expression = parse_expression(line)
	if isinstance(expression, CallExpression): return CallStatement(expression)
	else: raise Exception("Inline statement must be call or assignment.")

def parse_inline_statement(line: str) -> Statement:
	match = re.match(r"^\s*(\w[\w\d\.]*)\s*=\s*(.*)", line)
	if match != None: return parse_assign_statement(line)
	match = re.match(r"^\s*(\w[\w\d\.]*)\s*\(", line)
	if match != None: return parse_call_statement(line)
	raise Exception("Invalid inline statement.")

def parse_statement(statement: Union[str, list]) -> Union[Statement, None]:
	if isinstance(statement, str):
		if len(statement.strip()) > 0:
			for key in _statements:
				if re.match("^\\s*" + key + "(\\s+.*)?$", statement, re.IGNORECASE) != None:
					return _statements[key](statement)
			return parse_inline_statement(statement)
		else:
			return None
	else:
		for key in _blocks:
			if re.match("^\\s*END\s+" + key + "\\s*$", statement[len(statement) - 1], re.IGNORECASE) != None:
				return _blocks[key](statement)
		raise Exception("Unknown block type or missing end statement.")

def parse_module(name: str, lines: "list[str]") -> Module:
	blockTree = collect_blocks(lines, True)[0]

	for i in range(len(blockTree)):
		if isinstance(blockTree[i], str) and len(blockTree[i].strip()) == 0: blockTree[i] = None
		else: blockTree[i] = parse_statement(blockTree[i])

	types = []
	code = []
	for info in blockTree:
		if isinstance(info, Type): types.append(info)
		elif isinstance(info, Callable): code.append(info)
		elif info == None: pass
		else: raise Exception(type(info).__name__ + " is not valid at the root level.")

	return Module(name, types, code)

def parse_file(file: str) -> Module:
	name = os.path.basename(file)

	if "." in name: name = re.sub(r"\.[^\.]+$", "", name)

	nameMatch = re.match(r"\w[\w\d]*", name)
	if nameMatch == None: raise Exception("Invalid module name \"" + name + "\".")

	stream = open(file, "r")
	lines = stream.readlines()
	stream.close()

	return parse_module(name, lines)

_statements["CALL"] = None
_statements["RETURN"] = parse_return_statement
_statements["DIM"] = parse_local_statement
_statements["ASM"] = parse_asm_statement

_blocks["SUB"] = parse_subroutine
_blocks["FUNCTION"] = parse_function
_blocks["STRUCTURE"] = parse_struct
_blocks["IF"] = None
_blocks["WHILE"] = None
_blocks["FOR"] = None
_blocks["TRY"] = None