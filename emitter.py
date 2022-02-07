from abc import abstractmethod

def _get_abstract_methods(object):
	result = []
	for member in dir(object):
		method = getattr(object, member)
		if callable(method) and getattr(method, "__isabstractmethod__", False):
			result.append(member)
	return result

class Label:
	def __init__(self, name="", address=None):
		self._name = name
		self._address = address
	
	def get_name(self):
		return self._name

	def set_name(self, name):
		self._name = name
	
	def get_address(self):
		return self._address
	
	def set_address(self, address):
		self._address = address
	
	def is_marked(self):
		return self._address != None

class Emitter():
	def __init__(self):
		abstracts = _get_abstract_methods(self)
		if len(abstracts) > 0:
			raise NotImplementedError("The following members have not been implemented: " + ", ".join(abstracts))

	@abstractmethod
	def emit_raw(self, operation, operands):
		"""Emit the specified raw instruction."""

	@abstractmethod
	def comment(self, text):
		"""Emit a comment in the resulting assembly."""

	@abstractmethod
	def push(self, immediate):
		"""Push the specified immediate to the stack."""

	@abstractmethod
	def pop(self):
		"""Pop value from the stack."""

	@abstractmethod
	def add(self):
		"""Pop value2 and value1 from the stack and push the sum."""

	@abstractmethod
	def sub(self):
		"""Pop value2 and value1 from the stack and push the difference."""

	@abstractmethod
	def mul_s(self):
		"""Pop value2 and value1 from the stack and push the signed multiplied result."""

	@abstractmethod
	def mul_u(self):
		"""Pop value2 and value1 from the stack and push the unsigned multiplied result."""

	@abstractmethod
	def div_s(self):
		"""Pop value2 and value1 from the stack and push the signed divided result."""

	@abstractmethod
	def div_u(self):
		"""Pop value2 and value1 from the stack and push the unsigned divided result."""

	@abstractmethod
	def rem_s(self):
		"""Pop value2 and value1 from the stack and push the signed remainder."""

	@abstractmethod
	def rem_u(self):
		"""Pop value2 and value1 from the stack and push the unsigned remainder."""

	@abstractmethod
	def bit_not(self):
		"""Pop value from the stack and push the bitwise not."""

	@abstractmethod
	def bit_and(self):
		"""Pop value2 and value1 from the stack and push the bitwise and."""

	@abstractmethod
	def bit_or(self):
		"""Pop value2 and value1 from the stack and push the bitwise or."""

	@abstractmethod
	def bit_xor(self):
		"""Pop value2 and value1 from the stack and push the bitwise xor."""

	@abstractmethod
	def lsh(self):
		"""Pop value2 and value1 from the stack and push the left shifted result."""

	@abstractmethod
	def rsh(self):
		"""Pop value2 and value1 from the stack and push the right shifted result."""

	@abstractmethod
	def cmp_eq(self):
		"""Pop value2 and value1 from the stack and push the equality comparison."""

	@abstractmethod
	def cmp_ne(self):
		"""Pop value2 and value1 from the stack and push the inequality comparison."""

	@abstractmethod
	def cmp_lt_s(self):
		"""Pop value2 and value1 from the stack and push the signed less than comparison."""

	@abstractmethod
	def cmp_lt_u(self):
		"""Pop value2 and value1 from the stack and push the unsigned less than comparison."""

	@abstractmethod
	def cmp_gt_s(self):
		"""Pop value2 and value1 from the stack and push the signed greater than comparison."""

	@abstractmethod
	def cmp_gt_u(self):
		"""Pop value2 and value1 from the stack and push the unsigned greater than comparison."""

	@abstractmethod
	def cmp_le_s(self):
		"""Pop value2 and value1 from the stack and push the signed less than or equal comparison."""

	@abstractmethod
	def cmp_le_u(self):
		"""Pop value2 and value1 from the stack and push the unsigned less than or equal comparison."""

	@abstractmethod
	def cmp_ge_s(self):
		"""Pop value2 and value1 from the stack and push the signed greater than or equal comparison."""

	@abstractmethod
	def cmp_ge_u(self):
		"""Pop value2 and value1 from the stack and push the unsigned greater than or equal comparison."""

	@abstractmethod
	def call(self, target):
		"""Call the specified target."""
	
	@abstractmethod
	def ret(self):
		"""Return to the address on the stack."""

	@abstractmethod
	def jmp(self, target):
		"""Jump to specified target."""

	@abstractmethod
	def br_t(self, target):
		"""Branch to specified target if value is not zero."""

	@abstractmethod
	def br_f(self, target):
		"""Branch to specified target if value is zero."""

	@abstractmethod
	def br_eq(self, target):
		"""Pop value2 and value1 from the stack and branch if the equality comparison is true."""

	@abstractmethod
	def br_ne(self, target):
		"""Pop value2 and value1 from the stack and branch if the inequality comparison is true."""

	@abstractmethod
	def br_lt_s(self, target):
		"""Pop value2 and value1 from the stack and branch if the signed less than comparison is true."""

	@abstractmethod
	def br_lt_u(self, target):
		"""Pop value2 and value1 from the stack and branch if the unsigned less than comparison is true."""

	@abstractmethod
	def br_gt_s(self, target):
		"""Pop value2 and value1 from the stack and branch if the signed greater than comparison is true."""

	@abstractmethod
	def br_gt_u(self, target):
		"""Pop value2 and value1 from the stack and branch if the unsigned greater than comparison is true."""

	@abstractmethod
	def br_le_s(self, target):
		"""Pop value2 and value1 from the stack and branch if the signed less than or equal comparison is true."""

	@abstractmethod
	def br_le_u(self, target):
		"""Pop value2 and value1 from the stack and branch if the unsigned less than or equal comparison is true."""

	@abstractmethod
	def br_ge_s(self, target):
		"""Pop value2 and value1 from the stack and branch if the signed greater than or equal comparison is true."""

	@abstractmethod
	def br_ge_u(self, target):
		"""Pop value2 and value1 from the stack and branch if the unsigned greater than or equal comparison is true."""

	@abstractmethod
	def add_sp(self, offset):
		"""Move the stack pointer up (pushing direction) the stack by the specified amount."""

	@abstractmethod
	def rem_sp(self, offset):
		"""Move the stack pointer down (popping direction) the stack by the specified amount."""

	@abstractmethod
	def ld_sp(self):
		"""Push the value of the stack pointer."""

	@abstractmethod
	def st_sp(self):
		"""Pop the value into the stack pointer."""

	@abstractmethod
	def ld_bp(self):
		"""Push the value of the base pointer."""

	@abstractmethod
	def st_bp(self):
		"""Pop the value into the base pointer."""

	@abstractmethod
	def ld_global(self, index):
		"""Load value from the specified global."""

	@abstractmethod
	def st_global(self, index):
		"""Store value in the specified global."""
	
	@abstractmethod
	def ld_ptr(self, size):
		"""Load value with the specified size at value and push it onto the stack."""
	
	@abstractmethod
	def st_ptr(self, size):
		"""Pop value1 with the specified size and store it at value2."""

	@abstractmethod
	def get_current_offset(self):
		"""Returns the number of instructions that have been emitted."""

	@abstractmethod
	def _emit_label(self, label):
		"""Called when a label is marked at the current location."""

	def create_label(self, name=""):
		return Label(name)
	
	def mark_label(self, label):
		label.set_address(self.get_current_offset())
		self._emit_label(label)