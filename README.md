# GeneralBasic
A stack-based systems language that supports structures, functions, expressions, and user-defined operator behaviour. Currently compiles to URCL with plans to add additional formats in the future.

## Why Python?
The initial implementation of this compiler is written in Python. This allowed for flexibility during development and guaranteed portability across major platforms. This compiler may be ported to other languages in the future should the need arise.

## Invoking the Compiler
```
python gb.py -o MyProgram.urcl MyProgram.gb
```
|Argument|Description|
|--------|-----------|
|gb.py|This is the main compiler script.|
|-o|This is the output flag, which indicates the argument that should be used for the name of the output file.|
|MyProgram.urcl|The name of the output file.|
|MyProgram.gb|The name of an input source file. Multiple source files can be included.|

## GeneralBasic Syntax
### Structures
Structures are a data type that can store multiple pieces of information, called fields.
```
Structure Ball
	Dim X As Integer
	Dim Y As Integer
End Structure
```
### Pointers
Pointers are declared by adding an asterisk (*) to the end of the referenced type name.
```
Dim ballAddress As Ball*
```
A pointer can be dereferenced by using the `ValueOf` operator.
```
Dim ballAddress As Ball*

...

Dim ball As Ball
ball = ValueOf(ballAddress)
```
A pointer to a variable can be obtained using the `AddressOf` operator.
```
Dim ball As Ball

...

Dim ballAddress As Ball*
ballAddress = AddressOf(ball)
```
### Type Casting
Type casting can be performed with the `As` operator.
```
Dim ballAddress As Ball*
ballAddress = 0x100 As Ball*
```
### Functions and Subroutines
Functions can be declared with pass-by-value parameters and a return value.
```
Function AddNumbers(a As Integer, b As Integer) As Integer
	Return a + b
End Function
```
If a return value is not required, a subroutine can be used instead.
```
Sub PrintNumbers(a As Integer, b As Integer)
	Print(a)
	Print(b)
End Sub
```
Parameters can be made to pass-by-reference by adding `ByRef` before the parameter name.
```
Sub Bounce(ByRef this As Ball)
	this.Y = this.Y * -1
End Sub
```
### Inline Assembly
Inline assembly allows for custom operations not supported by the compiler to be implemented on the target platform. Each command is prefixed with the `Asm` keyword followed by one of three command names: `Load`, `Save`, or `Exec`.

`Load` accepts one variable as an argument and pushes it onto the local stack.

`Save` accepts one variable as an argument and pops a value from the local stack into it.

`Exec` accepts one or more arguments and emits them as a raw instruction.
```
Sub AddOne(ByRef value As Integer)
	Asm Load value
	Asm Exec pop R1
	Asm Exec inc R1 R1
	Asm Exec psh R1
	Asm Save value
End Sub
```
Inline assembly statements are not exempt from emitter-level optimization and may be simplified or modified in cases such as extraneous stack operations or unused registers. Care should be taken to not modify the program's base pointer, as doing so could lead to unexpected or unsafe behaviour.