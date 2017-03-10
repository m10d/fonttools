"""psCharStrings.py -- module implementing various kinds of CharStrings:
CFF dictionary data and Type1/Type2 CharStrings.
"""

from __future__ import print_function, division, absolute_import
from fontTools.misc.py23 import *
from fontTools.misc.fixedTools import fixedToFloat
import struct
import logging


log = logging.getLogger(__name__)


def read_operator(self, b0, data, index):
	if b0 == 12:
		op = (b0, byteord(data[index]))
		index = index+1
	else:
		op = b0
	try:
		operator = self.operators[op]
	except KeyError:
		return None, index
	value = self.handle_operator(operator)
	return value, index

def read_byte(self, b0, data, index):
	return b0 - 139, index

def read_smallInt1(self, b0, data, index):
	b1 = byteord(data[index])
	return (b0-247)*256 + b1 + 108, index+1

def read_smallInt2(self, b0, data, index):
	b1 = byteord(data[index])
	return -(b0-251)*256 - b1 - 108, index+1

def read_shortInt(self, b0, data, index):
	value, = struct.unpack(">h", data[index:index+2])
	return value, index+2

def read_longInt(self, b0, data, index):
	value, = struct.unpack(">l", data[index:index+4])
	return value, index+4

def read_fixed1616(self, b0, data, index):
	value, = struct.unpack(">l", data[index:index+4])
	return fixedToFloat(value, precisionBits=16), index+4

def read_reserved(self, b0, data, index):
	assert NotImplementedError
	return NotImplemented, index

def read_realNumber(self, b0, data, index):
	number = ''
	while True:
		b = byteord(data[index])
		index = index + 1
		nibble0 = (b & 0xf0) >> 4
		nibble1 = b & 0x0f
		if nibble0 == 0xf:
			break
		number = number + realNibbles[nibble0]
		if nibble1 == 0xf:
			break
		number = number + realNibbles[nibble1]
	return float(number), index


t1OperandEncoding = [None] * 256
t1OperandEncoding[0:32] = (32) * [read_operator]
t1OperandEncoding[32:247] = (247 - 32) * [read_byte]
t1OperandEncoding[247:251] = (251 - 247) * [read_smallInt1]
t1OperandEncoding[251:255] = (255 - 251) * [read_smallInt2]
t1OperandEncoding[255] = read_longInt
assert len(t1OperandEncoding) == 256

t2OperandEncoding = t1OperandEncoding[:]
t2OperandEncoding[28] = read_shortInt
t2OperandEncoding[255] = read_fixed1616

cffDictOperandEncoding = t2OperandEncoding[:]
cffDictOperandEncoding[29] = read_longInt
cffDictOperandEncoding[30] = read_realNumber
cffDictOperandEncoding[255] = read_reserved


realNibbles = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
		'.', 'E', 'E-', None, '-']
realNibblesDict = {v:i for i,v in enumerate(realNibbles)}

maxOpStack = 193


class ByteCodeBase(object):
	pass


def buildOperatorDict(operatorList):
	oper = {}
	opc = {}
	for item in operatorList:
		if len(item) == 2:
			oper[item[0]] = item[1]
		else:
			oper[item[0]] = item[1:]
		if isinstance(item[0], tuple):
			opc[item[1]] = item[0]
		else:
			opc[item[1]] = (item[0],)
	return oper, opc


t2Operators = [
#	opcode		name
	(1,		'hstem'),
	(3,		'vstem'),
	(4,		'vmoveto'),
	(5,		'rlineto'),
	(6,		'hlineto'),
	(7,		'vlineto'),
	(8,		'rrcurveto'),
	(10,		'callsubr'),
	(11,		'return'),
	(14,		'endchar'),

	(16,		'blend'),
	(18,		'hstemhm'),
	(19,		'hintmask'),
	(20,		'cntrmask'),
	(21,		'rmoveto'),
	(22,		'hmoveto'),
	(23,		'vstemhm'),
	(24,		'rcurveline'),
	(25,		'rlinecurve'),
	(26,		'vvcurveto'),
	(27,		'hhcurveto'),
#	(28,		'shortint'),  # not really an operator
	(29,		'callgsubr'),
	(30,		'vhcurveto'),
	(31,		'hvcurveto'),
	((12, 0),	'ignore'),	# dotsection. Yes, there a few very early OTF/CFF
							# fonts with this deprecated operator. Just ignore it.
	((12, 3),	'and'),
	((12, 4),	'or'),
	((12, 5),	'not'),
	((12, 8),	'store'),
	((12, 9),	'abs'),
	((12, 10),	'add'),
	((12, 11),	'sub'),
	((12, 12),	'div'),
	((12, 13),	'load'),
	((12, 14),	'neg'),
	((12, 15),	'eq'),
	((12, 18),	'drop'),
	((12, 20),	'put'),
	((12, 21),	'get'),
	((12, 22),	'ifelse'),
	((12, 23),	'random'),
	((12, 24),	'mul'),
	((12, 26),	'sqrt'),
	((12, 27),	'dup'),
	((12, 28),	'exch'),
	((12, 29),	'index'),
	((12, 30),	'roll'),
	((12, 34),	'hflex'),
	((12, 35),	'flex'),
	((12, 36),	'hflex1'),
	((12, 37),	'flex1'),
]

CFF2Operators = [entry for entry in t2Operators if ((isinstance(entry[0], int) or
											(entry[0][1] < 34)) and (not entry[0] in [11,14])) ]
CFF2Operators.extend(
[
	(15,		'vsindex'),
	(16,		'blend'),
])

def sortOps(entry):
	opCode = entry[0]
	if isinstance(opCode, int):
		opCode = (opCode,)
	return opCode

CFF2Operators.sort(key=sortOps)

def getIntEncoder(format):
	if format == "cff":
		fourByteOp = bytechr(29)
	elif format == "t1":
		fourByteOp = bytechr(255)
	else:
		assert format == "t2"
		fourByteOp = None

	def encodeInt(value, fourByteOp=fourByteOp, bytechr=bytechr,
			pack=struct.pack, unpack=struct.unpack):
		if -107 <= value <= 107:
			code = bytechr(value + 139)
		elif 108 <= value <= 1131:
			value = value - 108
			code = bytechr((value >> 8) + 247) + bytechr(value & 0xFF)
		elif -1131 <= value <= -108:
			value = -value - 108
			code = bytechr((value >> 8) + 251) + bytechr(value & 0xFF)
		elif fourByteOp is None:
			# T2 only supports 2 byte ints
			if -32768 <= value <= 32767:
				code = bytechr(28) + pack(">h", value)
			else:
				# Backwards compatible hack: due to a previous bug in FontTools,
				# 16.16 fixed numbers were written out as 4-byte ints. When
				# these numbers were small, they were wrongly written back as
				# small ints instead of 4-byte ints, breaking round-tripping.
				# This here workaround doesn't do it any better, since we can't
				# distinguish anymore between small ints that were supposed to
				# be small fixed numbers and small ints that were just small
				# ints. Hence the warning.
				import sys
				sys.stderr.write("Warning: 4-byte T2 number got passed to the "
					"IntType handler. This should happen only when reading in "
					"old XML files.\n")
				code = bytechr(255) + pack(">l", value)
		else:
			code = fourByteOp + pack(">l", value)
		return code

	return encodeInt


encodeIntCFF = getIntEncoder("cff")
encodeIntT1 = getIntEncoder("t1")
encodeIntT2 = getIntEncoder("t2")

def encodeFixed(f, pack=struct.pack):
	# For T2 only
	return b"\xff" + pack(">l", int(round(f * 65536)))

def encodeFloat(f):
	# For CFF only, used in cffLib
	s = str(f).upper()
	if s[:2] == "0.":
		s = s[1:]
	elif s[:3] == "-0.":
		s = "-" + s[2:]
	nibbles = []
	while s:
		c = s[0]
		s = s[1:]
		if c == "E" and s[:1] == "-":
			s = s[1:]
			c = "E-"
		nibbles.append(realNibblesDict[c])
	nibbles.append(0xf)
	if len(nibbles) % 2:
		nibbles.append(0xf)
	d = bytechr(30)
	for i in range(0, len(nibbles), 2):
		d = d + bytechr(nibbles[i] << 4 | nibbles[i+1])
	return d


class CharStringCompileError(Exception): pass


class SimpleT2Decompiler(object):

	def __init__(self, localSubrs, globalSubrs):
		self.localSubrs = localSubrs
		self.localBias = calcSubrBias(localSubrs)
		self.globalSubrs = globalSubrs
		self.globalBias = calcSubrBias(globalSubrs)
		self.reset()

	def reset(self):
		self.callingStack = []
		self.operandStack = []
		self.hintCount = 0
		self.hintMaskBytes = 0

	def check_program(self, program):
		assert program, "illegal CharString: decompiled to empty program"
		assert program[-1] in ("endchar", "return", "callsubr", "callgsubr",
				"seac"), "illegal CharString"

	def execute(self, charString):
		self.callingStack.append(charString)
		needsDecompilation = charString.needsDecompilation()
		if needsDecompilation:
			program = []
			pushToProgram = program.append
		else:
			pushToProgram = lambda x: None
		pushToStack = self.operandStack.append
		index = 0
		while True:
			token, isOperator, index = charString.getToken(index)
			if token is None:
				break  # we're done!
			pushToProgram(token)
			if isOperator:
				handlerName = "op_" + token
				handler = getattr(self, handlerName, None)
				if handler is not None:
					rv = handler(index)
					if rv:
						hintMaskBytes, index = rv
						pushToProgram(hintMaskBytes)
				else:
					self.popall()
			else:
				pushToStack(token)
		if needsDecompilation:
			self.check_program(program)
			charString.setProgram(program)
		del self.callingStack[-1]

	def pop(self):
		value = self.operandStack[-1]
		del self.operandStack[-1]
		return value

	def popall(self):
		stack = self.operandStack[:]
		self.operandStack[:] = []
		return stack

	def push(self, value):
		self.operandStack.append(value)

	def op_return(self, index):
		if self.operandStack:
			pass

	def op_endchar(self, index):
		pass

	def op_ignore(self, index):
		pass

	def op_callsubr(self, index):
		subrIndex = self.pop()
		subr = self.localSubrs[subrIndex+self.localBias]
		self.execute(subr)

	def op_callgsubr(self, index):
		subrIndex = self.pop()
		subr = self.globalSubrs[subrIndex+self.globalBias]
		self.execute(subr)

	def op_hstem(self, index):
		self.countHints()
	def op_vstem(self, index):
		self.countHints()
	def op_hstemhm(self, index):
		self.countHints()
	def op_vstemhm(self, index):
		self.countHints()

	def op_hintmask(self, index):
		if not self.hintMaskBytes:
			self.countHints()
			self.hintMaskBytes = (self.hintCount + 7) // 8
		hintMaskBytes, index = self.callingStack[-1].getBytes(index, self.hintMaskBytes)
		return hintMaskBytes, index

	op_cntrmask = op_hintmask

	def countHints(self):
		args = self.popall()
		self.hintCount = self.hintCount + len(args) // 2

	# misc
	def op_and(self, index):
		raise NotImplementedError
	def op_or(self, index):
		raise NotImplementedError
	def op_not(self, index):
		raise NotImplementedError
	def op_store(self, index):
		raise NotImplementedError
	def op_abs(self, index):
		raise NotImplementedError
	def op_add(self, index):
		raise NotImplementedError
	def op_sub(self, index):
		raise NotImplementedError
	def op_div(self, index):
		raise NotImplementedError
	def op_load(self, index):
		raise NotImplementedError
	def op_neg(self, index):
		raise NotImplementedError
	def op_eq(self, index):
		raise NotImplementedError
	def op_drop(self, index):
		raise NotImplementedError
	def op_put(self, index):
		raise NotImplementedError
	def op_get(self, index):
		raise NotImplementedError
	def op_ifelse(self, index):
		raise NotImplementedError
	def op_random(self, index):
		raise NotImplementedError
	def op_mul(self, index):
		raise NotImplementedError
	def op_sqrt(self, index):
		raise NotImplementedError
	def op_dup(self, index):
		raise NotImplementedError
	def op_exch(self, index):
		raise NotImplementedError
	def op_index(self, index):
		raise NotImplementedError
	def op_roll(self, index):
		raise NotImplementedError


class SimpleCFF2Decompiler(SimpleT2Decompiler):
	def __init__(self, localSubrs, globalSubrs, private = None):
		super(SimpleCFF2Decompiler, self).__init__(localSubrs, globalSubrs)
		self.private = private

	def reset(self):
		super(SimpleCFF2Decompiler, self).reset()
		self.numRegions = 0

	def check_program(self, program):
		if program:
			assert program[-1] not in ("seac"), "illegal CharString Terminator"

	def op_blend(self, index):
		if self.numRegions == 0:
			self.numRegions = self.private.getNumRegions()
		numBlends = self.pop()
		numOps = numBlends*self.numRegions
		blendArgs = self.operandStack[-numOps:]
		del self.operandStack[:-(numOps-numBlends)] # Leave the default operands on the stack.


	def op_vsindex(self, index):
		vi = self.pop()
		self.numRegions = self.private.getNumRegions(vi)



t1Operators = [
#	opcode		name
	(1,		'hstem'),
	(3,		'vstem'),
	(4,		'vmoveto'),
	(5,		'rlineto'),
	(6,		'hlineto'),
	(7,		'vlineto'),
	(8,		'rrcurveto'),
	(9,		'closepath'),
	(10,		'callsubr'),
	(11,		'return'),
	(13,		'hsbw'),
	(14,		'endchar'),
	(21,		'rmoveto'),
	(22,		'hmoveto'),
	(30,		'vhcurveto'),
	(31,		'hvcurveto'),
	((12, 0),	'dotsection'),
	((12, 1),	'vstem3'),
	((12, 2),	'hstem3'),
	((12, 6),	'seac'),
	((12, 7),	'sbw'),
	((12, 12),	'div'),
	((12, 16),	'callothersubr'),
	((12, 17),	'pop'),
	((12, 33),	'setcurrentpoint'),
]


class T2WidthExtractor(SimpleT2Decompiler):

	def __init__(self, localSubrs, globalSubrs, nominalWidthX, defaultWidthX):
		SimpleT2Decompiler.__init__(self, localSubrs, globalSubrs)
		self.nominalWidthX = nominalWidthX
		self.defaultWidthX = defaultWidthX

	def reset(self):
		SimpleT2Decompiler.reset(self)
		self.gotWidth = 0
		self.width = 0

	def popallWidth(self, evenOdd=0):
		args = self.popall()
		if not self.gotWidth:
			if evenOdd ^ (len(args) % 2):
				self.width = self.nominalWidthX + args[0]
				args = args[1:]
			else:
				self.width = self.defaultWidthX
			self.gotWidth = 1
		return args

	def countHints(self):
		args = self.popallWidth()
		self.hintCount = self.hintCount + len(args) // 2

	def op_rmoveto(self, index):
		self.popallWidth()

	def op_hmoveto(self, index):
		self.popallWidth(1)

	def op_vmoveto(self, index):
		self.popallWidth(1)

	def op_endchar(self, index):
		self.popallWidth()


class T2OutlineExtractor(T2WidthExtractor):

	def __init__(self, pen, localSubrs, globalSubrs, nominalWidthX, defaultWidthX):
		T2WidthExtractor.__init__(
			self, localSubrs, globalSubrs, nominalWidthX, defaultWidthX)
		self.pen = pen

	def reset(self):
		T2WidthExtractor.reset(self)
		self.currentPoint = (0, 0)
		self.sawMoveTo = 0

	def _nextPoint(self, point):
		x, y = self.currentPoint
		point = x + point[0], y + point[1]
		self.currentPoint = point
		return point

	def rMoveTo(self, point):
		self.pen.moveTo(self._nextPoint(point))
		self.sawMoveTo = 1

	def rLineTo(self, point):
		if not self.sawMoveTo:
			self.rMoveTo((0, 0))
		self.pen.lineTo(self._nextPoint(point))

	def rCurveTo(self, pt1, pt2, pt3):
		if not self.sawMoveTo:
			self.rMoveTo((0, 0))
		nextPoint = self._nextPoint
		self.pen.curveTo(nextPoint(pt1), nextPoint(pt2), nextPoint(pt3))

	def closePath(self):
		if self.sawMoveTo:
			self.pen.closePath()
		self.sawMoveTo = 0

	def endPath(self):
		# In T2 there are no open paths, so always do a closePath when
		# finishing a sub path.
		self.closePath()

	#
	# hint operators
	#
	#def op_hstem(self, index):
	#	self.countHints()
	#def op_vstem(self, index):
	#	self.countHints()
	#def op_hstemhm(self, index):
	#	self.countHints()
	#def op_vstemhm(self, index):
	#	self.countHints()
	#def op_hintmask(self, index):
	#	self.countHints()
	#def op_cntrmask(self, index):
	#	self.countHints()

	#
	# path constructors, moveto
	#
	def op_rmoveto(self, index):
		self.endPath()
		self.rMoveTo(self.popallWidth())
	def op_hmoveto(self, index):
		self.endPath()
		self.rMoveTo((self.popallWidth(1)[0], 0))
	def op_vmoveto(self, index):
		self.endPath()
		self.rMoveTo((0, self.popallWidth(1)[0]))
	def op_endchar(self, index):
		self.endPath()
		args = self.popallWidth()
		if args:
			from fontTools.encodings.StandardEncoding import StandardEncoding
			# endchar can do seac accent bulding; The T2 spec says it's deprecated,
			# but recent software that shall remain nameless does output it.
			adx, ady, bchar, achar = args
			baseGlyph = StandardEncoding[bchar]
			self.pen.addComponent(baseGlyph, (1, 0, 0, 1, 0, 0))
			accentGlyph = StandardEncoding[achar]
			self.pen.addComponent(accentGlyph, (1, 0, 0, 1, adx, ady))

	#
	# path constructors, lines
	#
	def op_rlineto(self, index):
		args = self.popall()
		for i in range(0, len(args), 2):
			point = args[i:i+2]
			self.rLineTo(point)

	def op_hlineto(self, index):
		self.alternatingLineto(1)
	def op_vlineto(self, index):
		self.alternatingLineto(0)

	#
	# path constructors, curves
	#
	def op_rrcurveto(self, index):
		"""{dxa dya dxb dyb dxc dyc}+ rrcurveto"""
		args = self.popall()
		for i in range(0, len(args), 6):
			dxa, dya, dxb, dyb, dxc, dyc, = args[i:i+6]
			self.rCurveTo((dxa, dya), (dxb, dyb), (dxc, dyc))

	def op_rcurveline(self, index):
		"""{dxa dya dxb dyb dxc dyc}+ dxd dyd rcurveline"""
		args = self.popall()
		for i in range(0, len(args)-2, 6):
			dxb, dyb, dxc, dyc, dxd, dyd = args[i:i+6]
			self.rCurveTo((dxb, dyb), (dxc, dyc), (dxd, dyd))
		self.rLineTo(args[-2:])

	def op_rlinecurve(self, index):
		"""{dxa dya}+ dxb dyb dxc dyc dxd dyd rlinecurve"""
		args = self.popall()
		lineArgs = args[:-6]
		for i in range(0, len(lineArgs), 2):
			self.rLineTo(lineArgs[i:i+2])
		dxb, dyb, dxc, dyc, dxd, dyd = args[-6:]
		self.rCurveTo((dxb, dyb), (dxc, dyc), (dxd, dyd))

	def op_vvcurveto(self, index):
		"dx1? {dya dxb dyb dyc}+ vvcurveto"
		args = self.popall()
		if len(args) % 2:
			dx1 = args[0]
			args = args[1:]
		else:
			dx1 = 0
		for i in range(0, len(args), 4):
			dya, dxb, dyb, dyc = args[i:i+4]
			self.rCurveTo((dx1, dya), (dxb, dyb), (0, dyc))
			dx1 = 0

	def op_hhcurveto(self, index):
		"""dy1? {dxa dxb dyb dxc}+ hhcurveto"""
		args = self.popall()
		if len(args) % 2:
			dy1 = args[0]
			args = args[1:]
		else:
			dy1 = 0
		for i in range(0, len(args), 4):
			dxa, dxb, dyb, dxc = args[i:i+4]
			self.rCurveTo((dxa, dy1), (dxb, dyb), (dxc, 0))
			dy1 = 0

	def op_vhcurveto(self, index):
		"""dy1 dx2 dy2 dx3 {dxa dxb dyb dyc dyd dxe dye dxf}* dyf? vhcurveto (30)
		{dya dxb dyb dxc dxd dxe dye dyf}+ dxf? vhcurveto
		"""
		args = self.popall()
		while args:
			args = self.vcurveto(args)
			if args:
				args = self.hcurveto(args)

	def op_hvcurveto(self, index):
		"""dx1 dx2 dy2 dy3 {dya dxb dyb dxc dxd dxe dye dyf}* dxf?
		{dxa dxb dyb dyc dyd dxe dye dxf}+ dyf?
		"""
		args = self.popall()
		while args:
			args = self.hcurveto(args)
			if args:
				args = self.vcurveto(args)

	#
	# path constructors, flex
	#
	def op_hflex(self, index):
		dx1, dx2, dy2, dx3, dx4, dx5, dx6 = self.popall()
		dy1 = dy3 = dy4 = dy6 = 0
		dy5 = -dy2
		self.rCurveTo((dx1, dy1), (dx2, dy2), (dx3, dy3))
		self.rCurveTo((dx4, dy4), (dx5, dy5), (dx6, dy6))
	def op_flex(self, index):
		dx1, dy1, dx2, dy2, dx3, dy3, dx4, dy4, dx5, dy5, dx6, dy6, fd = self.popall()
		self.rCurveTo((dx1, dy1), (dx2, dy2), (dx3, dy3))
		self.rCurveTo((dx4, dy4), (dx5, dy5), (dx6, dy6))
	def op_hflex1(self, index):
		dx1, dy1, dx2, dy2, dx3, dx4, dx5, dy5, dx6 = self.popall()
		dy3 = dy4 = 0
		dy6 = -(dy1 + dy2 + dy3 + dy4 + dy5)

		self.rCurveTo((dx1, dy1), (dx2, dy2), (dx3, dy3))
		self.rCurveTo((dx4, dy4), (dx5, dy5), (dx6, dy6))
	def op_flex1(self, index):
		dx1, dy1, dx2, dy2, dx3, dy3, dx4, dy4, dx5, dy5, d6 = self.popall()
		dx = dx1 + dx2 + dx3 + dx4 + dx5
		dy = dy1 + dy2 + dy3 + dy4 + dy5
		if abs(dx) > abs(dy):
			dx6 = d6
			dy6 = -dy
		else:
			dx6 = -dx
			dy6 = d6
		self.rCurveTo((dx1, dy1), (dx2, dy2), (dx3, dy3))
		self.rCurveTo((dx4, dy4), (dx5, dy5), (dx6, dy6))

	#
	# MultipleMaster. Well...
	#
	def op_blend(self, index):
		self.popall()

	# misc
	def op_and(self, index):
		raise NotImplementedError
	def op_or(self, index):
		raise NotImplementedError
	def op_not(self, index):
		raise NotImplementedError
	def op_store(self, index):
		raise NotImplementedError
	def op_abs(self, index):
		raise NotImplementedError
	def op_add(self, index):
		raise NotImplementedError
	def op_sub(self, index):
		raise NotImplementedError
	def op_div(self, index):
		num2 = self.pop()
		num1 = self.pop()
		d1 = num1//num2
		d2 = num1/num2
		if d1 == d2:
			self.push(d1)
		else:
			self.push(d2)
	def op_load(self, index):
		raise NotImplementedError
	def op_neg(self, index):
		raise NotImplementedError
	def op_eq(self, index):
		raise NotImplementedError
	def op_drop(self, index):
		raise NotImplementedError
	def op_put(self, index):
		raise NotImplementedError
	def op_get(self, index):
		raise NotImplementedError
	def op_ifelse(self, index):
		raise NotImplementedError
	def op_random(self, index):
		raise NotImplementedError
	def op_mul(self, index):
		raise NotImplementedError
	def op_sqrt(self, index):
		raise NotImplementedError
	def op_dup(self, index):
		raise NotImplementedError
	def op_exch(self, index):
		raise NotImplementedError
	def op_index(self, index):
		raise NotImplementedError
	def op_roll(self, index):
		raise NotImplementedError

	#
	# miscellaneous helpers
	#
	def alternatingLineto(self, isHorizontal):
		args = self.popall()
		for arg in args:
			if isHorizontal:
				point = (arg, 0)
			else:
				point = (0, arg)
			self.rLineTo(point)
			isHorizontal = not isHorizontal

	def vcurveto(self, args):
		dya, dxb, dyb, dxc = args[:4]
		args = args[4:]
		if len(args) == 1:
			dyc = args[0]
			args = []
		else:
			dyc = 0
		self.rCurveTo((0, dya), (dxb, dyb), (dxc, dyc))
		return args

	def hcurveto(self, args):
		dxa, dxb, dyb, dyc = args[:4]
		args = args[4:]
		if len(args) == 1:
			dxc = args[0]
			args = []
		else:
			dxc = 0
		self.rCurveTo((dxa, 0), (dxb, dyb), (dxc, dyc))
		return args

class CFF2OutlineExtractor(T2OutlineExtractor):
	pass

class T1OutlineExtractor(T2OutlineExtractor):

	def __init__(self, pen, subrs):
		self.pen = pen
		self.subrs = subrs
		self.reset()

	def reset(self):
		self.flexing = 0
		self.width = 0
		self.sbx = 0
		T2OutlineExtractor.reset(self)

	def endPath(self):
		if self.sawMoveTo:
			self.pen.endPath()
		self.sawMoveTo = 0

	def popallWidth(self, evenOdd=0):
		return self.popall()

	def exch(self):
		stack = self.operandStack
		stack[-1], stack[-2] = stack[-2], stack[-1]

	#
	# path constructors
	#
	def op_rmoveto(self, index):
		if self.flexing:
			return
		self.endPath()
		self.rMoveTo(self.popall())
	def op_hmoveto(self, index):
		if self.flexing:
			# We must add a parameter to the stack if we are flexing
			self.push(0)
			return
		self.endPath()
		self.rMoveTo((self.popall()[0], 0))
	def op_vmoveto(self, index):
		if self.flexing:
			# We must add a parameter to the stack if we are flexing
			self.push(0)
			self.exch()
			return
		self.endPath()
		self.rMoveTo((0, self.popall()[0]))
	def op_closepath(self, index):
		self.closePath()
	def op_setcurrentpoint(self, index):
		args = self.popall()
		x, y = args
		self.currentPoint = x, y

	def op_endchar(self, index):
		self.endPath()

	def op_hsbw(self, index):
		sbx, wx = self.popall()
		self.width = wx
		self.sbx = sbx
		self.currentPoint = sbx, self.currentPoint[1]
	def op_sbw(self, index):
		self.popall()  # XXX

	#
	def op_callsubr(self, index):
		subrIndex = self.pop()
		subr = self.subrs[subrIndex]
		self.execute(subr)
	def op_callothersubr(self, index):
		subrIndex = self.pop()
		nArgs = self.pop()
		#print nArgs, subrIndex, "callothersubr"
		if subrIndex == 0 and nArgs == 3:
			self.doFlex()
			self.flexing = 0
		elif subrIndex == 1 and nArgs == 0:
			self.flexing = 1
		# ignore...
	def op_pop(self, index):
		pass  # ignore...

	def doFlex(self):
		finaly = self.pop()
		finalx = self.pop()
		self.pop()	# flex height is unused

		p3y = self.pop()
		p3x = self.pop()
		bcp4y = self.pop()
		bcp4x = self.pop()
		bcp3y = self.pop()
		bcp3x = self.pop()
		p2y = self.pop()
		p2x = self.pop()
		bcp2y = self.pop()
		bcp2x = self.pop()
		bcp1y = self.pop()
		bcp1x = self.pop()
		rpy = self.pop()
		rpx = self.pop()

		# call rrcurveto
		self.push(bcp1x+rpx)
		self.push(bcp1y+rpy)
		self.push(bcp2x)
		self.push(bcp2y)
		self.push(p2x)
		self.push(p2y)
		self.op_rrcurveto(None)

		# call rrcurveto
		self.push(bcp3x)
		self.push(bcp3y)
		self.push(bcp4x)
		self.push(bcp4y)
		self.push(p3x)
		self.push(p3y)
		self.op_rrcurveto(None)

		# Push back final coords so subr 0 can find them
		self.push(finalx)
		self.push(finaly)

	def op_dotsection(self, index):
		self.popall()  # XXX
	def op_hstem3(self, index):
		self.popall()  # XXX
	def op_seac(self, index):
		"asb adx ady bchar achar seac"
		from fontTools.encodings.StandardEncoding import StandardEncoding
		asb, adx, ady, bchar, achar = self.popall()
		baseGlyph = StandardEncoding[bchar]
		self.pen.addComponent(baseGlyph, (1, 0, 0, 1, 0, 0))
		accentGlyph = StandardEncoding[achar]
		adx = adx + self.sbx - asb  # seac weirdness
		self.pen.addComponent(accentGlyph, (1, 0, 0, 1, adx, ady))
	def op_vstem3(self, index):
		self.popall()  # XXX

class T2CharString(ByteCodeBase):

	operandEncoding = t2OperandEncoding
	operators, opcodes = buildOperatorDict(t2Operators)
	decompilerClass = SimpleT2Decompiler
	outlineExtractor = T2OutlineExtractor

	def __init__(self, bytecode=None, program=None, private=None, globalSubrs=None):
		if program is None:
			program = []
		self.bytecode = bytecode
		self.program = program
		self.private = private
		self.globalSubrs = globalSubrs if globalSubrs is not None else []

	def __repr__(self):
		if self.bytecode is None:
			return "<%s (source) at %x>" % (self.__class__.__name__, id(self))
		else:
			return "<%s (bytecode) at %x>" % (self.__class__.__name__, id(self))

	def getIntEncoder(self):
		return encodeIntT2

	def getFixedEncoder(self):
		return encodeFixed

	def decompile(self):
		if not self.needsDecompilation():
			return
		subrs = getattr(self.private, "Subrs", [])
		decompiler = self.decompilerClass(subrs, self.globalSubrs)
		decompiler.execute(self)

	def draw(self, pen):
		subrs = getattr(self.private, "Subrs", [])
		extractor = self.outlineExtractor(pen, subrs, self.globalSubrs,
				self.private.nominalWidthX, self.private.defaultWidthX)
		extractor.execute(self)
		self.width = extractor.width

	def check_program(self, program):
		assert self.program, "illegal CharString: decompiled to empty program"
		assert self.program[-1] in ("endchar", "return", "callsubr", "callgsubr",
				"seac"), "illegal CharString"

	def compile(self):
		if self.bytecode is not None:
			return
		opcodes = self.opcodes
		program = self.program
		self.check_program(program)
		bytecode = []
		encodeInt = self.getIntEncoder()
		encodeFixed = self.getFixedEncoder()
		i = 0
		end = len(program)
		while i < end:
			token = program[i]
			i = i + 1
			tp = type(token)
			if issubclass(tp, basestring):
				try:
					bytecode.extend(bytechr(b) for b in opcodes[token])
				except KeyError:
					raise CharStringCompileError("illegal operator: %s" % token)
				if token in ('hintmask', 'cntrmask'):
					bytecode.append(program[i])  # hint mask
					i = i + 1
			elif tp == int:
				bytecode.append(encodeInt(token))
			elif tp == float:
				bytecode.append(encodeFixed(token))
			else:
				assert 0, "unsupported type: %s" % tp
		try:
			bytecode = bytesjoin(bytecode)
		except TypeError:
			log.error(bytecode)
			raise
		self.setBytecode(bytecode)

	def needsDecompilation(self):
		return self.bytecode is not None

	def setProgram(self, program):
		self.program = program
		self.bytecode = None

	def setBytecode(self, bytecode):
		self.bytecode = bytecode
		self.program = None

	def getToken(self, index,
			len=len, byteord=byteord, basestring=basestring,
			isinstance=isinstance):
		if self.bytecode is not None:
			if index >= len(self.bytecode):
				return None, 0, 0
			b0 = byteord(self.bytecode[index])
			index = index + 1
			handler = self.operandEncoding[b0]
			token, index = handler(self, b0, self.bytecode, index)
		else:
			if index >= len(self.program):
				return None, 0, 0
			token = self.program[index]
			index = index + 1
		isOperator = isinstance(token, basestring)
		return token, isOperator, index

	def getBytes(self, index, nBytes):
		if self.bytecode is not None:
			newIndex = index + nBytes
			bytes = self.bytecode[index:newIndex]
			index = newIndex
		else:
			bytes = self.program[index]
			index = index + 1
		assert len(bytes) == nBytes
		return bytes, index

	def handle_operator(self, operator):
		return operator

	def toXML(self, xmlWriter):
		from fontTools.misc.textTools import num2binary
		if self.bytecode is not None:
			xmlWriter.dumphex(self.bytecode)
		else:
			index = 0
			args = []
			while True:
				token, isOperator, index = self.getToken(index)
				if token is None:
					break
				if isOperator:
					args = [str(arg) for arg in args]
					if token in ('hintmask', 'cntrmask'):
						hintMask, isOperator, index = self.getToken(index)
						bits = []
						for byte in hintMask:
							bits.append(num2binary(byteord(byte), 8))
						hintMask = strjoin(bits)
						line = ' '.join(args + [token, hintMask])
					else:
						line = ' '.join(args + [token])
					xmlWriter.write(line)
					xmlWriter.newline()
					args = []
				else:
					args.append(token)

	def fromXML(self, name, attrs, content):
		from fontTools.misc.textTools import binary2num, readHex
		if attrs.get("raw"):
			self.setBytecode(readHex(content))
			return
		content = strjoin(content)
		content = content.split()
		program = []
		end = len(content)
		i = 0
		while i < end:
			token = content[i]
			i = i + 1
			try:
				token = int(token)
			except ValueError:
				try:
					token = float(token)
				except ValueError:
					program.append(token)
					if token in ('hintmask', 'cntrmask'):
						mask = content[i]
						maskBytes = b""
						for j in range(0, len(mask), 8):
							maskBytes = maskBytes + bytechr(binary2num(mask[j:j+8]))
						program.append(maskBytes)
						i = i + 1
				else:
					program.append(token)
			else:
				program.append(token)
		self.setProgram(program)

class CFF2CharString(T2CharString):

	operandEncoding = t2OperandEncoding
	operators, opcodes = buildOperatorDict(CFF2Operators)
	decompilerClass = SimpleCFF2Decompiler
	outlineExtractor = CFF2OutlineExtractor

	def check_program(self, program):
		#assert self.program, "illegal CharString: decompiled to empty program"
		# Empty program is OK for CFF2 Charstring - same a T2 with only an endchar.
		if self.program:
			assert self.program[-1] not in ("seac"), "illegal CFF2 CharString Termination"

	def compile(self):
		# Remove endchar, if there is one.
		super(CFF2CharString, self).compile()
		if self.bytecode and (byteord(self.bytecode[-1]) in (11, 14)):
			self.bytecode = self.bytecode[:-1]

	def decompile(self):
		# Remove endchar, if there is one.
		if not self.needsDecompilation():
			return
		subrs = getattr(self.private, "Subrs", [])
		decompiler = self.decompilerClass(subrs, self.globalSubrs, self.private)
		decompiler.execute(self)

class CFF2SubrCharString(CFF2CharString):
	pass


class T1CharString(T2CharString):

	operandEncoding = t1OperandEncoding
	operators, opcodes = buildOperatorDict(t1Operators)

	def __init__(self, bytecode=None, program=None, subrs=None):
		if program is None:
			program = []
		self.bytecode = bytecode
		self.program = program
		self.subrs = subrs

	def getIntEncoder(self):
		return encodeIntT1

	def getFixedEncoder(self):
		def encodeFixed(value):
			raise TypeError("Type 1 charstrings don't support floating point operands")

	def decompile(self):
		if self.bytecode is None:
			return
		program = []
		index = 0
		while True:
			token, isOperator, index = self.getToken(index)
			if token is None:
				break
			program.append(token)
		self.setProgram(program)

	def draw(self, pen):
		extractor = T1OutlineExtractor(pen, self.subrs)
		extractor.execute(self)
		self.width = extractor.width


class DictDecompiler(ByteCodeBase):

	operandEncoding = cffDictOperandEncoding

	def __init__(self, strings):
		self.stack = []
		self.strings = strings
		self.dict = {}

	def getDict(self):
		assert len(self.stack) == 0, "non-empty stack"
		return self.dict

	def decompile(self, data):
		index = 0
		lenData = len(data)
		push = self.stack.append
		while index < lenData:
			b0 = byteord(data[index])
			index = index + 1
			handler = self.operandEncoding[b0]
			value, index = handler(self, b0, data, index)
			if value is not None:
				push(value)
	def pop(self):
		value = self.stack[-1]
		del self.stack[-1]
		return value

	def popall(self):
		args = self.stack[:]
		del self.stack[:]
		return args

	def handle_operator(self, operator):
		operator, argType = operator
		if isinstance(argType, tuple):
			value = ()
			for i in range(len(argType)-1, -1, -1):
				arg = argType[i]
				arghandler = getattr(self, "arg_" + arg)
				value = (arghandler(operator),) + value
		else:
			arghandler = getattr(self, "arg_" + argType)
			value = arghandler(operator)
		if operator == "blend":
			self.stack.extend(value)
		else:
			self.dict[operator] = value

	def arg_number(self, name):
		if isinstance(self.stack[0], list):
			out = self.arg_blend_number(self.stack)
		else:
			out = self.pop()
		return out

	def arg_blend_number(self, name):
		out = []
		blendArgs = self.pop()
		numMasters = len(blendArgs)
		out.append(blendArgs)
		out.append("blend")
		dummy = self.popall()
		return blendArgs

	def arg_SID(self, name):
		return self.strings[self.pop()]
	def arg_array(self, name):
		return self.popall()
	def arg_blendList(self, name):
		# The last item on the stack is the number of return values, aka numValues.
		# before that we have [numValues: args from first master]
		# then numValues blend lists, where each blend list is numMasters -1
		# Total number of values is numValues + (numValues * (numMasters -1)), == numValues * numMasters.
		# reformat list to be numReturnValues tuples, each tuple with nMaster values
		numReturnValues = self.pop()
		args = self.popall()
		numArgs = len(args)
		vsindex = self.dict.get('vsindex', 0)
		numMasters = self.parent.getNumRegions(vsindex) # only a PrivateDict has blended ops.
		value = [None]*numReturnValues
		numDeltas = numMasters-1
		i = 0
		prevVal = 0
		prevValueList = [0]*numMasters
		while i < numReturnValues:
			newVal = args[i] + prevVal
			blendList = [newVal]*numMasters
			prevVal = newVal
			value[i] = blendList
			j = 1
			while j < numMasters:
				masterOffset = numReturnValues + (i* numDeltas)
				mi = masterOffset +(j-1)
				delta = args[i] + args[mi]
				blendList[j]= delta + prevValueList[j]
				j += 1
			prevValueList = blendList
			i += 1
		return value

	def arg_delta(self, name):
		valueList = self.popall()
		out = []
		if valueList and isinstance(valueList[0], list):
			# arg_blendList() has already converted these to absolute values.
			out = valueList
		else:
			current = 0
			for v in valueList:
				current = current + v
				out.append(current)
		return out


def calcSubrBias(subrs):
	nSubrs = len(subrs)
	if nSubrs < 1240:
		bias = 107
	elif nSubrs < 33900:
		bias = 1131
	else:
		bias = 32768
	return bias
