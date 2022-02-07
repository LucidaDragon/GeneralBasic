from abc import ABCMeta, abstractmethod
from typing import Callable, Union
import inspect, re

from emitter import Emitter
from compiler import parse_value

def is_readonly_reg_instruction(inst: "list[str]") -> bool:
	return inst[0].startswith(".") or inst[0].startswith("//") or re.match(r"(B(R[ELGZ])|([LG]E)|(N[EZ]))|(JMP)|(CAL)|(PSH)|(STR)", inst[0].upper()) != None

def get_constant_operand(operand: Union[str, int, None]) -> Union[int, None]:
	if isinstance(operand, int): return operand
	elif isinstance(operand, str):
		try: return int(operand)
		except: pass
	return None

class StackOptimizer(metaclass=ABCMeta):
	@abstractmethod
	def get_regex(self) -> str: ...
	@abstractmethod
	def optimize(self, i: int, insts: "list[list[str]]", get_reg: Callable[[str], Union[str, int, None]], set_reg: Callable[[str, Union[str, int, None]], None], registers: "dict[str, Union[str, int, None]]", stack: "list[Union[str, int, None]]") -> None: ...

class MonoOptimizer(metaclass=ABCMeta):
	@abstractmethod
	def get_regex(self) -> str: ...
	@abstractmethod
	def optimize(self, i: int, insts: "list[list[str]]") -> bool: ...

class PairOptimizer(metaclass=ABCMeta):
	@abstractmethod
	def get_regex_current(self) -> str: ...
	@abstractmethod
	def get_regex_next(self) -> str: ...
	def get_allow_labels_next(self) -> bool: return False
	@abstractmethod
	def optimize(self, current: int, next: int, insts: "list[list[str]]") -> bool: ...

class CodeOptimizer(metaclass=ABCMeta):
	@abstractmethod
	def optimize(self, insts: "list[list[str]]") -> bool: ...

class PushStackOptimizer(StackOptimizer):
	def get_regex(self) -> str: return "PSH"
	def optimize(self, i: int, insts: "list[list[str]]", get_reg: Callable[[str], Union[str, int, None]], set_reg: Callable[[str, Union[str, int, None]], None], registers: "dict[str, Union[str, int, None]]", stack: "list[Union[str, int, None]]") -> None:
		try:
			stack.append(parse_value(insts[i][1]))
			insts[i] = ["nop"]
		except:
			value = insts[i][1]
			if isinstance(value, int):
				stack.append(value)
				insts[i] = ["nop"]
			elif isinstance(value, str):
				if value.upper().startswith("R") or value.upper() == "SP": stack.append(get_reg(value))
				else: stack.append(value)

class PopStackOptimizer(StackOptimizer):
	def get_regex(self) -> str: return "POP"
	def optimize(self, i: int, insts: "list[list[str]]", get_reg: Callable[[str], Union[str, int, None]], set_reg: Callable[[str, Union[str, int, None]], None], registers: "dict[str, Union[str, int, None]]", stack: "list[Union[str, int, None]]") -> None:
		value = stack.pop() if len(stack) > 0 else None
		if get_reg(insts[i][1]) == value and value != None:
			insts[i] = ["pop", "R0"]
		else:
			set_reg(insts[i][1], value)
		if isinstance(value, int): insts[i] = ["nop"]

class GeneralStackOptimizer(StackOptimizer):
	def get_regex(self) -> str: return "\w.*"
	def optimize(self, i: int, insts: "list[list[str]]", get_reg: Callable[[str], Union[str, int, None]], set_reg: Callable[[str, Union[str, int, None]], None], registers: "dict[str, Union[str, int, None]]", stack: "list[Union[str, int, None]]") -> None:
		registersReadOnly = is_readonly_reg_instruction(insts[i])
		for j in range(1 if registersReadOnly else 2, len(insts[i])):
			value = get_reg(insts[i][j])
			if isinstance(value, int): insts[i][j] = str(value)
			elif value == "BP": insts[i][j] = "R3"
		if len(insts[i]) > 1:
			if insts[i][0].upper() == "CAL":
				registers.clear()
			elif not registersReadOnly:
				if insts[i][1] == "SP":
					def _bad_modification(): raise RuntimeError("This type of stack modification is not allowed.")
					if len(insts[i]) == 4 and insts[i][2].upper() == "SP" and get_constant_operand(insts[i][3]) != None:
						if insts[i][0].upper() == "ADD":
							for _ in range(get_constant_operand(insts[i][3])):
								if len(stack) > 0: stack.pop()
								else: raise RuntimeError("Virtual stack underflow.")
						elif insts[i][0].upper() == "SUB":
							for _ in range(get_constant_operand(insts[i][3])):
								stack.append(None)
						else:
							_bad_modification()
					elif len(insts[i]) == 4 and insts[i][2].upper() == "R3" and get_constant_operand(insts[i][3]) != None:
						if insts[i][0].upper() == "SUB":
							newStackLength = get_constant_operand(insts[i][3]) + 1
							while len(stack) > newStackLength:
								if len(stack) > 0: stack.pop()
								else: raise RuntimeError("Virtual stack underflow.")
						else:
							_bad_modification()
					else:
						_bad_modification()
				set_reg(insts[i][1], None)
		elif insts[i][0].upper() == "RET":
			registers.clear()
			registers["SP"] = "BP"

class StackVerificationOptimizer(StackOptimizer):
	def get_regex(self) -> str: return "RET"
	def optimize(self, i: int, insts: "list[list[str]]", get_reg: Callable[[str], Union[str, int, None]], set_reg: Callable[[str, Union[str, int, None]], None], registers: "dict[str, Union[str, int, None]]", stack: "list[Union[str, int, None]]") -> None:
		if len(stack) != 0: raise RuntimeError("Stack must be empty before returning.")

class PushFollowedByPopOptimizer(PairOptimizer):
	def get_regex_current(self) -> str: return "PSH"
	def get_regex_next(self) -> str: return "POP"
	def optimize(self, current: int, next: int, insts: "list[list[str]]") -> bool:
		if insts[next][1] == insts[current][1]: insts.pop(next)
		else: insts[next] = ["mov", insts[next][1], insts[current][1]]
		insts.pop(current)
		return True

class RepeatedAddAndSubtractOptimizer(PairOptimizer):
	def get_regex_current(self) -> str: return "(ADD)|(SUB)"
	def get_regex_next(self) -> str: return "(ADD)|(SUB)"
	def optimize(self, current: int, next: int, insts: "list[list[str]]") -> bool:
		if get_constant_operand(insts[current][3]) != None and get_constant_operand(insts[next][3]) != None:
			if insts[current][1] == insts[next][2] and insts[current][1] == insts[next][1]:
				a = get_constant_operand(insts[current][3])
				b = get_constant_operand(insts[next][3])
				if insts[current][0].upper() == "SUB": a = -a
				if insts[next][0].upper() == "SUB": b = -b
				value = a + b
				if value < 0: insts[current] = ["sub", insts[next][1], insts[current][2], str(-value)]
				elif value > 0: insts[current] = ["add", insts[next][1], insts[current][2], str(value)]
				else: insts[current] = ["mov", insts[next][1], insts[current][2]]
				insts.pop(next)
				return True
		return False

class OverwrittenResultOptimizer(PairOptimizer):
	def get_regex_current(self) -> str: return "\w.*"
	def get_regex_next(self) -> str: return "\w.*"
	def optimize(self, current: int, next: int, insts: "list[list[str]]") -> bool:
		if not (is_readonly_reg_instruction(insts[current]) or is_readonly_reg_instruction(insts[next])):
			if len(insts[current]) > 1 and len(insts[next]) > 1 and insts[current][1] == insts[next][1]:
				for i in range(2, len(insts[next])):
					if insts[next][i] == insts[current][1]: return False
				insts.pop(current)
				return True
		return False

class JumpNextOptimizer(PairOptimizer):
	def get_regex_current(self) -> str: return "JMP"
	def get_regex_next(self) -> str: return "\\..*"
	def get_allow_labels_next(self) -> bool: return True
	def optimize(self, current: int, next: int, insts: "list[list[str]]") -> bool:
		if insts[current][1] == insts[next][0]:
			insts.pop(current)
			return True
		return False

class VoidMoveOptimizer(MonoOptimizer):
	def get_regex(self) -> str: return "MOV"
	def optimize(self, i: int, insts: "list[list[str]]") -> bool:
		if insts[i][1] == insts[i][2] or insts[i][1] == "R0":
			insts.pop(i)
			return True
		return False

class CommentOptimizer(MonoOptimizer):
	def get_regex(self) -> str: return "//.*"
	def optimize(self, i: int, insts: "list[list[str]]") -> bool:
		insts.pop(i)
		return True

class LabelOptimizer(CodeOptimizer):
	def optimize(self, insts: "list[list[str]]") -> bool:
		rerun = False
		labels = []
		for i in range(len(insts)):
			if insts[i][0].startswith(".__"): labels.append([insts[i][0], i, 0])
		for inst in insts:
			if len(inst) > 1:
				for operand in inst[1:]:
					if operand.startswith(".__"):
						for i in range(len(labels)):
							if labels[i][0] == operand: labels[i][2] += 1
		offset = 0
		for label in labels:
			if label[2] == 0:
				rerun = True
				insts.pop(label[1] - offset)
				offset += 1
		return rerun

class URCLEmitter(Emitter):
	def __init__(self, showIL=False, optimize=True, optimizers=[PushStackOptimizer(), PopStackOptimizer(), GeneralStackOptimizer(), StackVerificationOptimizer(), PushFollowedByPopOptimizer(), RepeatedAddAndSubtractOptimizer(), OverwrittenResultOptimizer(), JumpNextOptimizer(), VoidMoveOptimizer(), LabelOptimizer()]):
		super().__init__()
		self._current = 0
		self._internal = 0
		self._insts = []
		self._showIL = showIL
		self._optimize = optimize
		self._optimizers = optimizers
	
	def _emit(self, *args):
		result = []
		for arg in args:
			if arg != None: result.append(arg)
		self._insts.append(result)

	def _target(self, target, internal=False):
		if isinstance(target, int) and internal: return ".___urcl___internal___" + str(target)
		elif isinstance(target, int): return ".___urcl___" + str(target)
		else: return "." + str(target)

	def _lcreate(self):
		self._internal += 1
		return self._internal - 1

	def _lmark(self, label):
		self._emit(self._target(label, True))

	def _next(self, index, allowLabels=False):
		for i in range(index + 1, len(self._insts)):
			if not ((self._insts[i][0].startswith(".") and not allowLabels) or self._insts[i][0].startswith("//") or self._insts[i][0].upper() == "NOP"):
				return i
		return None

	def get_current_offset(self):
		return self._current

	def commit(self, stream):
		if self._optimize:
			stack = []
			registers = { "SP": "BP" }
			def _get_reg(name: str):
				name = name.upper()
				if name == "R0": return 0
				elif name in registers: return registers[name]
				else: return None
			def _set_reg(name: str, value: Union[str, int, None]):
				name = name.upper()
				if name != "R0": registers[name] = value
			
			for i in range(len(self._insts)):
				for optimizer in self._optimizers:
					if isinstance(optimizer, StackOptimizer) and re.match(f"^{optimizer.get_regex()}$", self._insts[i][0].upper()) != None:
						optimizer.optimize(i, self._insts, _get_reg, _set_reg, registers, stack)
						break

			i = 0
			rerun = False
			while i < len(self._insts):
				rerun = False
				for optimizer in self._optimizers:
					if isinstance(optimizer, PairOptimizer):
						current = i
						next = self._next(i, optimizer.get_allow_labels_next())
						if next != None and re.match(f"^{optimizer.get_regex_current()}$", self._insts[current][0].upper()) != None and re.match(f"^{optimizer.get_regex_next()}$", self._insts[next][0].upper()) != None:
							if optimizer.optimize(current, next, self._insts):
								rerun = True
								break
					elif isinstance(optimizer, MonoOptimizer):
						if re.match(f"^{optimizer.get_regex()}$", self._insts[i][0].upper()) != None:
							if optimizer.optimize(i, self._insts):
								rerun = True
								break
				if rerun: i = 0
				else: i += 1
			
			rerun = True
			while rerun:
				rerun = False
				for optimizer in self._optimizers:
					if isinstance(optimizer, CodeOptimizer):
						rerun |= optimizer.optimize(self._insts)

		for inst in self._insts:
			if inst[0].upper() != "NOP": stream.write(" ".join(inst) + "\n")

	def comment(self, text):
		parts = text.split(" ")
		parts[0] = f"//{parts[0]}"
		self._emit(*parts)

	def begin_instruction(self):
		if self._showIL: self.comment(inspect.stack()[1].function)
		self._emit(self._target(self._current))
	
	def end_instruction(self):
		self._current += 1

	def emit_raw(self, operation, operands):
		self.begin_instruction()
		self._emit(*([operation] + operands))
		self.end_instruction()

	def push(self, immediate):
		self.begin_instruction()
		self._emit("psh", str(immediate))
		self.end_instruction()

	def pop(self):
		self.begin_instruction()
		self._emit("pop", "R0")
		self.end_instruction()

	def add(self):
		self.begin_instruction()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("add", "R1", "R1", "R2")
		self._emit("psh", "R1")
		self.end_instruction()

	def sub(self):
		self.begin_instruction()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("sub", "R1", "R1", "R2")
		self._emit("psh", "R1")
		self.end_instruction()

	def mul_s(self):
		self.mul_u()

	def mul_u(self):
		self.begin_instruction()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("mlt", "R1", "R1", "R2")
		self._emit("psh", "R1")
		self.end_instruction()

	def div_s(self):
		raise NotImplementedError()

	def div_u(self):
		self.begin_instruction()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("div", "R1", "R1", "R2")
		self._emit("psh", "R1")
		self.end_instruction()

	def rem_s(self):
		raise NotImplementedError()

	def rem_u(self):
		self.begin_instruction()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("mod", "R1", "R1", "R2")
		self._emit("psh", "R1")
		self.end_instruction()

	def bit_not(self):
		self.begin_instruction()
		self._emit("pop", "R1")
		self._emit("not", "R1", "R1")
		self._emit("psh", "R1")
		self.end_instruction()

	def bit_and(self):
		self.begin_instruction()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("and", "R1", "R1", "R2")
		self._emit("psh", "R1")
		self.end_instruction()

	def bit_or(self):
		self.begin_instruction()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("or", "R1", "R1", "R2")
		self._emit("psh", "R1")
		self.end_instruction()

	def bit_xor(self):
		self.begin_instruction()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("xor", "R1", "R1", "R2")
		self._emit("psh", "R1")
		self.end_instruction()

	def lsh(self):
		self.begin_instruction()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("bsl", "R1", "R1", "R2")
		self._emit("psh", "R1")
		self.end_instruction()

	def rsh(self):
		self.begin_instruction()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("bsr", "R1", "R1", "R2")
		self._emit("psh", "R1")
		self.end_instruction()

	def cmp_eq(self):
		self.begin_instruction()
		end = self._lcreate()
		true = self._lcreate()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("bre", self._target(true, True), "R1", "R2")
		self._emit("psh", "0")
		self._emit("jmp", self._target(end, True))
		self._lmark(true)
		self._emit("psh", "1")
		self._lmark(end)
		self.end_instruction()

	def cmp_ne(self):
		self.begin_instruction()
		end = self._lcreate()
		true = self._lcreate()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("bne", self._target(true, True), "R1", "R2")
		self._emit("psh", "0")
		self._emit("jmp", self._target(end, True))
		self._lmark(true)
		self._emit("psh", "1")
		self._lmark(end)
		self.end_instruction()

	def cmp_lt_s(self):
		raise NotImplementedError()

	def cmp_lt_u(self):
		self.begin_instruction()
		end = self._lcreate()
		true = self._lcreate()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("brl", self._target(true, True), "R1", "R2")
		self._emit("psh", "0")
		self._emit("jmp", self._target(end, True))
		self._lmark(true)
		self._emit("psh", "1")
		self._lmark(end)
		self.end_instruction()

	def cmp_gt_s(self):
		raise NotImplementedError()

	def cmp_gt_u(self):
		self.begin_instruction()
		end = self._lcreate()
		true = self._lcreate()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("brg", self._target(true, True), "R1", "R2")
		self._emit("psh", "0")
		self._emit("jmp", self._target(end, True))
		self._lmark(true)
		self._emit("psh", "1")
		self._lmark(end)
		self.end_instruction()

	def cmp_le_s(self):
		raise NotImplementedError()

	def cmp_le_u(self):
		self.begin_instruction()
		end = self._lcreate()
		true = self._lcreate()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("ble", self._target(true, True), "R1", "R2")
		self._emit("psh", "0")
		self._emit("jmp", self._target(end, True))
		self._lmark(true)
		self._emit("psh", "1")
		self._lmark(end)
		self.end_instruction()

	def cmp_ge_s(self):
		raise NotImplementedError()

	def cmp_ge_u(self):
		self.begin_instruction()
		end = self._lcreate()
		true = self._lcreate()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("bge", self._target(true, True), "R1", "R2")
		self._emit("psh", "0")
		self._emit("jmp", self._target(end, True))
		self._lmark(true)
		self._emit("psh", "1")
		self._lmark(end)
		self.end_instruction()

	def call(self, target):
		self.begin_instruction()
		self._emit("cal", self._target(target))
		self.end_instruction()
	
	def ret(self):
		self.begin_instruction()
		self._emit("ret")
		self.end_instruction()

	def jmp(self, target):
		self.begin_instruction()
		self._emit("jmp", self._target(target))
		self.end_instruction()

	def br_t(self, target):
		self.begin_instruction()
		self._emit("pop", "R1")
		self._emit("brz", self._target(target), "R1")
		self.end_instruction()

	def br_f(self, target):
		self.begin_instruction()
		self._emit("pop", "R1")
		self._emit("bnz", self._target(target), "R1")
		self.end_instruction()

	def br_eq(self, target):
		self.begin_instruction()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("bre", self._target(target), "R1", "R2")
		self.end_instruction()

	def br_ne(self, target):
		self.begin_instruction()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("bne", self._target(target), "R1", "R2")
		self.end_instruction()

	def br_lt_s(self, target):
		raise NotImplementedError()

	def br_lt_u(self, target):
		self.begin_instruction()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("brl", self._target(target), "R1", "R2")
		self.end_instruction()

	def br_gt_s(self, target):
		raise NotImplementedError()

	def br_gt_u(self, target):
		self.begin_instruction()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("brg", self._target(target), "R1", "R2")
		self.end_instruction()

	def br_le_s(self, target):
		raise NotImplementedError()

	def br_le_u(self, target):
		self.begin_instruction()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("ble", self._target(target), "R1", "R2")
		self.end_instruction()

	def br_ge_s(self, target):
		raise NotImplementedError()

	def br_ge_u(self, target):
		self.begin_instruction()
		self._emit("pop", "R2")
		self._emit("pop", "R1")
		self._emit("bge", self._target(target), "R1", "R2")
		self.end_instruction()

	def add_sp(self, offset):
		self.begin_instruction()
		self._emit("sub", "SP", "SP", str(offset))
		self.end_instruction()

	def rem_sp(self, offset):
		self.begin_instruction()
		self._emit("add", "SP", "SP", str(offset))
		self.end_instruction()

	def ld_sp(self):
		self.begin_instruction()
		self._emit("psh", "SP")
		self.end_instruction()

	def st_sp(self):
		self.begin_instruction()
		self._emit("pop", "SP")
		self.end_instruction()

	def ld_bp(self):
		self.begin_instruction()
		self._emit("psh", "R3")
		self.end_instruction()

	def st_bp(self):
		self.begin_instruction()
		self._emit("pop", "R3")
		self.end_instruction()
	
	def ld_ptr(self, size):
		self.begin_instruction()
		if size > 0:
			self._emit("pop", "R1")
			if size == 1:
				self._emit("lod", "R1", "R1")
				self._emit("psh", "R1")
			else:
				self._emit("add", "R1", "R1", str(size - 1))
				for i in range(size):
					if i != 0: self._emit("sub", "R1", "R1", "1")
					self._emit("lod", "R2", "R1")
					self._emit("psh", "R2")
		self.end_instruction()

	def st_ptr(self, size):
		self.begin_instruction()
		if size > 0:
			self._emit("pop", "R1")
			for i in range(size):
				if i != 0: self._emit("add", "R1", "R1", "1")
				self._emit("pop", "R2")
				self._emit("str", "R1", "R2")
		self.end_instruction()

	def ld_global(self, index):
		self.begin_instruction()
		self._emit("psh", "R" + str(index + 4))
		self.end_instruction()

	def st_global(self, index):
		self.begin_instruction()
		self._emit("pop", "R" + str(index + 4))
		self.end_instruction()

	def _emit_label(self, label):
		if len(label.get_name()) > 0: self._emit(self._target(label.get_name()))