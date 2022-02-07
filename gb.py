import sys
from compiler import AssemblyInstructionStatement, InlineBody, SignedInteger, UnsignedInteger, parse_file
from emitters.urcl import URCLEmitter

defaultTypes = [SignedInteger(), UnsignedInteger()]
defaultFunctions = [
	InlineBody("__CAST_Integer_UInteger", UnsignedInteger(), []),
	InlineBody("__CAST_UInteger_Integer", SignedInteger(), []),
	InlineBody("__ADD_Integer_Integer", SignedInteger(), [
		AssemblyInstructionStatement("pop", ["R2"]),
		AssemblyInstructionStatement("pop", ["R1"]),
		AssemblyInstructionStatement("add", ["R1", "R1", "R2"]),
		AssemblyInstructionStatement("psh", ["R1"])
	]),
	InlineBody("__SUB_Integer_Integer", SignedInteger(), [
		AssemblyInstructionStatement("pop", ["R2"]),
		AssemblyInstructionStatement("pop", ["R1"]),
		AssemblyInstructionStatement("sub", ["R1", "R1", "R2"]),
		AssemblyInstructionStatement("psh", ["R1"])
	]),
	InlineBody("__MUL_Integer_Integer", SignedInteger(), [
		AssemblyInstructionStatement("pop", ["R2"]),
		AssemblyInstructionStatement("pop", ["R1"]),
		AssemblyInstructionStatement("mul", ["R1", "R1", "R2"]),
		AssemblyInstructionStatement("psh", ["R1"])
	]),
	InlineBody("__DIV_Integer_Integer", SignedInteger(), [
		AssemblyInstructionStatement("pop", ["R2"]),
		AssemblyInstructionStatement("pop", ["R1"]),
		AssemblyInstructionStatement("sdiv", ["R1", "R1", "R2"]),
		AssemblyInstructionStatement("psh", ["R1"])
	]),
	InlineBody("__LSHIFT_Integer_Integer", SignedInteger(), [
		AssemblyInstructionStatement("pop", ["R2"]),
		AssemblyInstructionStatement("pop", ["R1"]),
		AssemblyInstructionStatement("sbsl", ["R1", "R1", "R2"]),
		AssemblyInstructionStatement("psh", ["R1"])
	]),
	InlineBody("__RSHIFT_Integer_Integer", SignedInteger(), [
		AssemblyInstructionStatement("pop", ["R2"]),
		AssemblyInstructionStatement("pop", ["R1"]),
		AssemblyInstructionStatement("sbsr", ["R1", "R1", "R2"]),
		AssemblyInstructionStatement("psh", ["R1"])
	]),
	InlineBody("__AND_Integer_Integer", SignedInteger(), [
		AssemblyInstructionStatement("pop", ["R2"]),
		AssemblyInstructionStatement("pop", ["R1"]),
		AssemblyInstructionStatement("and", ["R1", "R1", "R2"]),
		AssemblyInstructionStatement("psh", ["R1"])
	]),
	InlineBody("__OR_Integer_Integer", SignedInteger(), [
		AssemblyInstructionStatement("pop", ["R2"]),
		AssemblyInstructionStatement("pop", ["R1"]),
		AssemblyInstructionStatement("or", ["R1", "R1", "R2"]),
		AssemblyInstructionStatement("psh", ["R1"])
	]),
	InlineBody("__XOR_Integer_Integer", SignedInteger(), [
		AssemblyInstructionStatement("pop", ["R2"]),
		AssemblyInstructionStatement("pop", ["R1"]),
		AssemblyInstructionStatement("xor", ["R1", "R1", "R2"]),
		AssemblyInstructionStatement("psh", ["R1"])
	]),
	InlineBody("__ADD_UInteger_UInteger", UnsignedInteger(), [
		AssemblyInstructionStatement("pop", ["R2"]),
		AssemblyInstructionStatement("pop", ["R1"]),
		AssemblyInstructionStatement("add", ["R1", "R1", "R2"]),
		AssemblyInstructionStatement("psh", ["R1"])
	]),
	InlineBody("__SUB_UInteger_UInteger", UnsignedInteger(), [
		AssemblyInstructionStatement("pop", ["R2"]),
		AssemblyInstructionStatement("pop", ["R1"]),
		AssemblyInstructionStatement("sub", ["R1", "R1", "R2"]),
		AssemblyInstructionStatement("psh", ["R1"])
	]),
	InlineBody("__MUL_UInteger_UInteger", UnsignedInteger(), [
		AssemblyInstructionStatement("pop", ["R2"]),
		AssemblyInstructionStatement("pop", ["R1"]),
		AssemblyInstructionStatement("mul", ["R1", "R1", "R2"]),
		AssemblyInstructionStatement("psh", ["R1"])
	]),
	InlineBody("__DIV_UInteger_UInteger", UnsignedInteger(), [
		AssemblyInstructionStatement("pop", ["R2"]),
		AssemblyInstructionStatement("pop", ["R1"]),
		AssemblyInstructionStatement("div", ["R1", "R1", "R2"]),
		AssemblyInstructionStatement("psh", ["R1"])
	]),
	InlineBody("__LSHIFT_UInteger_UInteger", UnsignedInteger(), [
		AssemblyInstructionStatement("pop", ["R2"]),
		AssemblyInstructionStatement("pop", ["R1"]),
		AssemblyInstructionStatement("bsl", ["R1", "R1", "R2"]),
		AssemblyInstructionStatement("psh", ["R1"])
	]),
	InlineBody("__RSHIFT_UInteger_UInteger", UnsignedInteger(), [
		AssemblyInstructionStatement("pop", ["R2"]),
		AssemblyInstructionStatement("pop", ["R1"]),
		AssemblyInstructionStatement("bsr", ["R1", "R1", "R2"]),
		AssemblyInstructionStatement("psh", ["R1"])
	]),
	InlineBody("__AND_UInteger_UInteger", UnsignedInteger(), [
		AssemblyInstructionStatement("pop", ["R2"]),
		AssemblyInstructionStatement("pop", ["R1"]),
		AssemblyInstructionStatement("and", ["R1", "R1", "R2"]),
		AssemblyInstructionStatement("psh", ["R1"])
	]),
	InlineBody("__OR_UInteger_UInteger", UnsignedInteger(), [
		AssemblyInstructionStatement("pop", ["R2"]),
		AssemblyInstructionStatement("pop", ["R1"]),
		AssemblyInstructionStatement("or", ["R1", "R1", "R2"]),
		AssemblyInstructionStatement("psh", ["R1"])
	]),
	InlineBody("__XOR_UInteger_UInteger", UnsignedInteger(), [
		AssemblyInstructionStatement("pop", ["R2"]),
		AssemblyInstructionStatement("pop", ["R1"]),
		AssemblyInstructionStatement("xor", ["R1", "R1", "R2"]),
		AssemblyInstructionStatement("psh", ["R1"])
	])
]

flags = []
args = { "-o": "main.urcl" }
inputs = []
flag = ""
for arg in sys.argv[1:]:
	if arg.startswith("-"):
		flag = arg
		flags.append(arg)
	else:
		if flag == "":
			inputs.append(arg)
		else:
			args[flag] = arg
		flag = ""

if len(inputs) == 0:
	print("No input files specified.")
	exit(1)

modules = [parse_file(input) for input in inputs]

for module in modules: module.Resolve(module.GetResolver(defaultTypes, defaultFunctions))

emit = URCLEmitter()
for module in modules: module.Emit(emit)

stream = open(args["-o"], "w")
emit.commit(stream)
stream.close()