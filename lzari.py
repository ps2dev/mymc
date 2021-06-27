#
# lzari.py
#
# By Ross Ridge
#

"""
Implementation of Haruhiko Okumura's LZARI data compression algorithm
in Python.  Largely based on LZARI.C, one key difference is the use of
a two level dicitionary look up during compression rather than
LZARI.C's binary search tree.
"""

_SCCS_ID = "@(#) mysc lzari.py 1.6 12/10/04 19:07:53\n"

import sys
import array
import binascii
import string
import time
from bisect import bisect_right
from math import log

try:
	import ctypes
	import mymcsup
except ImportError:
	mymcsup = None

hexlify = binascii.hexlify

__ALL__ = ['lzari_codec', 'string_to_bit_array', 'bit_array_to_string']

#
# Fundamental constants of the LZARI compression alogorithm.
#
# Changing any of these values will create an incompatible implementation.
#

HIST_LEN = 4096
MIN_MATCH_LEN = 3
MAX_MATCH_LEN = 60

ARITH_BITS = 15
QUADRANT1 = 1 << ARITH_BITS
QUADRANT2 = QUADRANT1 * 2
QUADRANT3 = QUADRANT1 * 3
QUADRANT4 = QUADRANT1 * 4
MAX_CUM = QUADRANT1 - 1
MAX_CHAR = (256 + MAX_MATCH_LEN - MIN_MATCH_LEN + 1)

#
# Other constants specific to this implementation
#

MAX_SUFFIX_CHAIN = 50	# limit on how many identical suffixes to try to match

#def debug(value, msg):
#	print "@@@ %s %04x" % (msg, value)
debug = lambda value, msg: None

_tr_16 = string.maketrans("0123456789abcdef",
			  "\x00\x01\x02\x03"
			  "\x10\x11\x12\x13"
			  "\x20\x21\x22\x23"
			  "\x30\x31\x32\x33")
_tr_4 = string.maketrans("0123",
			 "\x00\x01"
			 "\x10\x11")
_tr_2 = string.maketrans("01", "\x00\x01")

def string_to_bit_array(s):
	"""Convert a string to an array containing a sequence of bits."""
	s = binascii.hexlify(s).translate(_tr_16)
	s = binascii.hexlify(s).translate(_tr_4)
	s = binascii.hexlify(s).translate(_tr_2)
	a = array.array('B', s)
	return a

_tr_rev_2 = string.maketrans("\x00\x01", "01")
_tr_rev_4 = string.maketrans("\x00\x01"
			     "\x10\x11",
			     "0123")
_tr_rev_16 = string.maketrans("\x00\x01\x02\x03"
			      "\x10\x11\x12\x13"
			      "\x20\x21\x22\x23"
			      "\x30\x31\x32\x33",
			      "0123456789abcdef")
def bit_array_to_string(a):
	"""Convert an array containing a sequence of bits to a string."""
	remainder = len(a) % 8
	if remainder != 0:
		a.fromlist([0] * (8 - remainder))
	s = a.tostring()
	s = binascii.unhexlify(s.translate(_tr_rev_2))
	s = binascii.unhexlify(s.translate(_tr_rev_4))	
	return binascii.unhexlify(s.translate(_tr_rev_16))

def _match(src, pos, hpos, mlen, end):
	mlen += 1
	if not src.startswith(src[hpos : hpos + mlen], pos):
		return None
	for i in range(mlen, end):
		if src[pos + i] != src[hpos + i]:
			return i
	return end

def _rehash_table2(src, chars, head, next, next2, hist_invalid):
	p = head
	table2 = {}
	l = []
	while p > hist_invalid:
		l.append(p)
		p = next[p % HIST_LEN]
	l.reverse()
	for p in l:
		p2 = p + MIN_MATCH_LEN
		key2 = src[p2 : p2 + chars]
		head2 = table2.get(key2, hist_invalid)
		next2[p % HIST_LEN] = head2
		table2[key2] = p
	return table2

class lzari_codec(object):
	# despite the name this does not implement a codec compatible
	# with Python's codec system
	
	def init(self, decode):
		self.high = QUADRANT4
		self.low = 0
		if decode:
			self.code = 0
			# reverse the order of sym_cum so bisect_right() can
			# be used for faster searching
			self.sym_cum = range(0, MAX_CHAR + 1)
		else:
			self.shifts = 0
			self.char_to_symbol = range(1, MAX_CHAR + 1)
			self.sym_cum = range(MAX_CHAR, -1, -1)
			self.next_table = [None] * HIST_LEN
			self.next2_table = [None] * HIST_LEN
			self.suffix_table = {}

		self.symbol_to_char = [0] + range(MAX_CHAR)
		self.sym_freq = [0] + [1] * MAX_CHAR
		self.position_cum = [0] * (HIST_LEN + 1)
		a = 0
		for i in range(HIST_LEN, 0, -1):
			a =  a + 10000 / (200 + i)
			self.position_cum[i - 1] = a
		
	def search(self, table, x):
		c = 1
	        s = len(table) - 1
		while True:
			a = (s + c) / 2
			if table[a] <= x:
				s = a
			else:
				c = a + 1
			if c >= s:
				break
		return c

	def update_model_decode(self, symbol):
		# A compatible implemention to the one used while compressing.
		
		sym_freq = self.sym_freq
		sym_cum = self.sym_cum
		
		if self.sym_cum[MAX_CHAR] >= MAX_CUM:
			c = 0
			for i in range(MAX_CHAR, 0, -1):
				self.sym_cum[MAX_CHAR - i] = c
				a = (self.sym_freq[i] + 1) / 2
				self.sym_freq[i] = a
				c += a
			self.sym_cum[MAX_CHAR] = c
		freq = sym_freq[symbol]
		new_symbol = symbol
		while self.sym_freq[new_symbol - 1] == freq:
		        new_symbol -= 1
		# new_symbol = sym_freq.index(freq)
		if new_symbol != symbol:
			symbol_to_char = self.symbol_to_char
		        swap_char = symbol_to_char[new_symbol]
			char = symbol_to_char[symbol]
			symbol_to_char[new_symbol] = char
			symbol_to_char[symbol] = swap_char
		sym_freq[new_symbol] = freq + 1
		for i in range(MAX_CHAR - new_symbol + 1, MAX_CHAR + 1):
			sym_cum[i] += 1
			
	def update_model_encode(self, symbol):
		sym_freq = self.sym_freq
		sym_cum = self.sym_cum
		
	        if sym_cum[0] >= MAX_CUM:
			c = 0
			for i in range(MAX_CHAR, 0, -1):
				sym_cum[i] = c
				a = (sym_freq[i] + 1) / 2
				sym_freq[i] = a
				c += a
			sym_cum[0] = c
		freq = sym_freq[symbol]
		new_symbol = symbol
		while sym_freq[new_symbol - 1] == freq:
		        new_symbol -= 1
		if new_symbol != symbol:
			debug(new_symbol, "a")
		        swap_char = self.symbol_to_char[new_symbol]
			char = self.symbol_to_char[symbol]
			self.symbol_to_char[new_symbol] = char
			self.symbol_to_char[symbol] = swap_char
			self.char_to_symbol[char] = new_symbol
			self.char_to_symbol[swap_char] = symbol
		sym_freq[new_symbol] += 1
		for i in range(new_symbol):
			sym_cum[i] += 1

	def decode_char(self):
		high = self.high
		low = self.low
		code = self.code
		sym_cum = self.sym_cum
		
		_range = high - low
		max_cum_freq = sym_cum[MAX_CHAR]
		n = ((code - low + 1) * max_cum_freq - 1) / _range
		i = bisect_right(sym_cum, n, 1)
		high = low + sym_cum[i] * _range / max_cum_freq
		low += sym_cum[i - 1] * _range / max_cum_freq
		symbol = MAX_CHAR + 1 - i

		while True:
			if low < QUADRANT2:
				if low < QUADRANT1 or high > QUADRANT3:
					if high > QUADRANT2:
						break
				else:
					low -= QUADRANT1
					code -= QUADRANT1
					high -= QUADRANT1
			else:
				low -= QUADRANT2
				code -= QUADRANT2
				high -= QUADRANT2
			low *= 2
			high *= 2
			code = code * 2 + self.in_iter()

		ret = self.symbol_to_char[symbol]
		self.high = high
		self.low = low
		self.code = code
		self.update_model_decode(symbol)
		return ret
	
	def decode_position(self):
		_range = self.high - self.low
		max_cum = self.position_cum[0]
		pos = self.search(self.position_cum,
				  ((self.code - self.low + 1)
				   * max_cum - 1) / _range) - 1
		self.high = (self.low +
			     self.position_cum[pos] * _range / max_cum)
		self.low += self.position_cum[pos + 1] * _range / max_cum
		while True:
			if self.low < QUADRANT2:
				if (self.low < QUADRANT1
				    or self.high > QUADRANT3):
					if self.high > QUADRANT2:
						return pos
 				else:
					self.low -= QUADRANT1
					self.code -= QUADRANT1
					self.high -= QUADRANT1
			else:
				self.low -= QUADRANT2
				self.code -= QUADRANT2
				self.high -= QUADRANT2
			self.low *= 2
			self.high *= 2
			self.code = self.in_iter() + self.code * 2

	def add_suffix_1(self, pos, find):
		# naive implemention used for testing
		
		if not find:
			return (None, 0)
		src = self.src
		mlen = min(1000, self.max_match, len(src) - pos)
		hist_start = max(pos - HIST_LEN, 0)
		while mlen >= MIN_MATCH_LEN:
			i = src.rfind(src[pos : pos + mlen], hist_start, pos)
			if i != -1:
				assert (src[pos : pos + mlen]
					== src[i: i + mlen])
				return (i, mlen)
			mlen -= 1
		return (None, -1)
			
	def add_suffix_2(self, pos, find):
		# a two level dictionary look up that leverages Python's
		# built-in dicts to get something that's hopefully faster
		# than implementing binary trees in completely in Python.
		
		src = self.src
		suffix_table = self.suffix_table
		max_match = min(self.max_match, len(src) - pos)

		mlen = -1
		mpos = None
		
		hist_invalid = pos - HIST_LEN - 1
		modpos = pos % HIST_LEN
		pos2 = pos + MIN_MATCH_LEN
		
		key = src[pos : pos2]
		a = suffix_table.get(key)
		if a != None:
			next = self.next_table
			next2 = self.next2_table
			
			[count, head, table2, chars] = a
			
			pos3 = pos2 + chars
			key2 = src[pos2 : pos3]
			min_match2 = MIN_MATCH_LEN + chars
			if find:
				p = table2.get(key2, hist_invalid)
				maxmlen = max_match - min_match2
				while p > hist_invalid and mlen != maxmlen:
					p3 = p + min_match2
					if mpos == None and p3 <= pos:
						mpos = p
						mlen = 0
					if p3 >= pos:
						p = next2[p % HIST_LEN]
						continue
					rlen = _match(src, pos3, p3, mlen,
						      min(maxmlen, pos - p3))
					if rlen != None:
						mpos = p
						mlen = rlen
					p = next2[p % HIST_LEN]
			if mpos != None:
				mlen += min_match2
			elif find:
				p = head
				maxmlen = min(chars, max_match - MIN_MATCH_LEN)
				i = 0
				while (p > hist_invalid and i < 50000
				       and mlen < maxmlen):
					assert i < count
					i += 1
					p2 = p + MIN_MATCH_LEN
					l2 = pos - p2
					if mpos == None and l2 >= 0:
						mpos = p
						mlen = 0
					if l2 <= 0:
						p = next[p % HIST_LEN]
						continue
					if l2 > maxmlen:
						l2 = maxmlen
					m = mlen + 1
					if src.startswith(src[p2 : p2 + m],
							  pos2):
						mpos = p
						for j in range(m, l2):
							if (src[pos2 + j]
							    != src[p2 + j]):
								mlen = j
								break
						else:
							mlen = l2
					#rlen = _match(src, pos2, p2, mlen, l2)
					#if rlen != None:
					#	mpos = p
					#	mlen = rlen
					p = next[p % HIST_LEN]
					
				if mpos != None:
					mlen += MIN_MATCH_LEN
					
			count += 1
			new_chars = int(log(count, 2))
			# new_chars = 50
			new_chars = min(new_chars, max_match - MIN_MATCH_LEN)
			if new_chars > chars:
				chars = new_chars
				table2 = _rehash_table2(src, chars, head,
							next, next2,
							hist_invalid)

			next[modpos] = head
			head = pos
			
			key2 = src[pos2 : pos2 + chars]
			head2 = table2.get(key2, hist_invalid)
			next2[modpos] = head2
			table2[key2] = pos

			a[0] = count
			a[1] = head
			a[2] = table2
			a[3] = chars
		else:
			self.next_table[modpos] = hist_invalid
			self.next2_table[modpos] = hist_invalid
			key2 = ""
			# key2 = src[pos2 : pos2 + 1]
			suffix_table[key] = [1, pos, {key2: pos}, len(key2)]

		p = pos - HIST_LEN
		if p >= 0:
			p2 = p + MIN_MATCH_LEN
			key = src[p : p2]
			a = suffix_table[key]
			(count, head, table2, chars) = a
			count -= 1
			if count == 0:
				assert head == p
				del suffix_table[key]
			else:
				key2 = src[p2 : p2 + chars]
				if table2[key2] == p:
					del table2[key2]
				a[0] = count
		assert (mpos == None
			or src[pos : pos + mlen] == src[mpos : mpos + mlen])
		return (mpos, mlen)

	def _add_suffix(self, pos, find):
		r = self.add_suffix_2(pos, find)
		start_pos = self.start_pos
		if find and r[0] != None:
			print ("%4d %02x %4d %2d"
			       % (pos - start_pos, ord(self.src[pos]),
				  r[0] - start_pos, r[1]))
		else:
			print ("%4d %02x"
				       % (pos - start_pos, ord(self.src[pos])))
		return r
	
	add_suffix = add_suffix_2
	
	def output_bit(self, bit):
		self.append_bit(bit)
		bit ^= 1
		for i in range(self.shifts):
			self.append_bit(bit)
		self.shifts = 0
		
	def encode_char(self, char):
		low = self.low
		high = self.high
		sym_cum = self.sym_cum
		
		symbol = self.char_to_symbol[char]
		range = high - low
	
		high = low + range * sym_cum[symbol - 1] / sym_cum[0]
		low += range * sym_cum[symbol] / sym_cum[0]
		debug(high, "high");
		debug(low, "low");
		while True:
			if high <= QUADRANT2:
				self.output_bit(0)
			elif low >= QUADRANT2:
				self.output_bit(1)
				low -= QUADRANT2
				high -= QUADRANT2
			elif low >= QUADRANT1 and high <= QUADRANT3:
				self.shifts += 1
				low -= QUADRANT1
				high -= QUADRANT1
			else:
				break
			low *= 2
			high *= 2
		self.low = low
		self.high = high
		self.update_model_encode(symbol)

	def encode_position(self, position):
		position_cum = self.position_cum
		low = self.low
		high = self.high

		range = high - low
		high = low + range * position_cum[position] / position_cum[0]
		low += range * position_cum[position + 1] / position_cum[0]

		debug(high, "high");
		debug(low, "low");
		while True:
			if high <= QUADRANT2:
				self.output_bit(0)
			elif low >= QUADRANT2:
				self.output_bit(1)
				low -= QUADRANT2
				high -= QUADRANT2
			elif low >= QUADRANT1 and high <= QUADRANT3:
				self.shifts += 1
				low -= QUADRANT1
				high -= QUADRANT1
			else:
				break
			low *= 2
			high *= 2
			
		self.low = low
		self.high = high
			
	def encode(self, src, progress = None):
		"""Compress a string."""
		
		length = len(src)
		if length == 0:
			return ""

		out_array = array.array('B')
		self.out_array = out_array
		self.append_bit = out_array.append
		
		self.init(False)

		max_match = min(MAX_MATCH_LEN, length)
		self.max_match = max_match
		self.src = src = "\x20" * max_match + src
			
		in_length = len(src)
		
		self.start_pos = max_match
		
		for in_pos in range(max_match):
			self.add_suffix(in_pos, False)
		in_pos += 1
		last_percent = -1
		while in_pos < in_length:
			if progress:
				percent = (in_pos - max_match) * 100 / length
				if percent != last_percent:
					sys.stderr.write("%s%3d%%\r"
							 % (progress, percent))
					last_percent = percent
			debug(ord(src[in_pos]), "src")
			(match_pos, match_len) = self.add_suffix(in_pos, True)
			if match_len < MIN_MATCH_LEN:
				self.encode_char(ord(src[in_pos]))
			else:
				debug(in_pos - match_pos - 1, "match_pos")
				debug(match_len, "match_len")
				self.encode_char(256 - MIN_MATCH_LEN
						 + match_len)
				self.encode_position(in_pos - match_pos - 1)
				for i in range(match_len - 1):
					in_pos += 1
					self.add_suffix(in_pos, False)
			in_pos += 1
				
		self.shifts += 1
		if self.low < QUADRANT1:
			self.output_bit(0)
		else:
			self.output_bit(1)

		#for k, v in sorted(self.suffix_table.items()):
		#	count, head, table2, chars = v
		#	print hexlify(k), count, head, len(table2), chars
			
		if progress:
			sys.stderr.write("%s100%%\n" % progress)
		
		return bit_array_to_string(out_array)
		
	def decode(self, src, out_length, progress = None):
		"""Decompress a string."""
		
		a = string_to_bit_array(src)
		a.fromlist([0] * 32)	 # add some extra bits 
		self.in_iter = iter(a).next

		out = array.array('B', "\0") * out_length
		outpos = 0
		
		self.init(True)

		self.code = 0
		for i in range(ARITH_BITS + 2):
			self.code += self.code + self.in_iter()

		hist_pos = HIST_LEN - MAX_MATCH_LEN
		history = [0x20] * hist_pos + [0] * MAX_MATCH_LEN

		decode_char = self.decode_char
		last_percent = -1
		last_time = time.time()
		while outpos < out_length:
			if progress:
				percent = outpos * 100 / out_length
				if percent != last_percent:
					now = time.time()
					if now - last_time >= 1:
						sys.stderr.write("%s%3d%%\r"
							% (progress, percent))
						last_percent = percent
						last_time = now
			char = decode_char()
			if char >= 0x100:
				pos = self.decode_position()
				length = char - 0x100 + MIN_MATCH_LEN
				base = (hist_pos - pos - 1) % HIST_LEN
				for off in range(length):
					a = history[(base + off) % HIST_LEN]
					out[outpos] = a
					outpos += 1
					history[hist_pos] = a
					hist_pos = (hist_pos + 1) % HIST_LEN
			else:
				out[outpos] = char
				outpos += 1
				history[hist_pos] = char
				hist_pos = (hist_pos + 1) % HIST_LEN
		
		self.in_iter = None
		if progress:
			sys.stderr.write("%s100%%\n" % progress)
		return out.tostring()

if mymcsup == None:
	def decode(src, out_length, progress = None):
		return lzari_codec().decode(src, out_length, progress)
	
	def encode(src, progress = None):
		return lzari_codec().encode(src, progress)
else:
	mylzari_decode = mymcsup.mylzari_decode
	mylzari_encode = mymcsup.mylzari_encode
	mylzari_free_encoded = mymcsup.mylzari_free_encoded
	
	def decode(src, out_length, progress = None):
		out = ctypes.create_string_buffer(out_length)
		if (mylzari_decode(src, len(src), out, out_length, progress)
		    == -1):
			raise ValueError, "compressed input is corrupt"
		return ctypes.string_at(out, out_length)

	def encode(src, progress = None):
		(r, compressed, comp_len) = mylzari_encode(src, len(src),
							   progress)
		# print r, compressed.value, comp_len
		if r == -1:
			raise MemoryError, "out of memory during compression"
		if compressed.value == None:
			return ""
		ret = ctypes.string_at(compressed.value, comp_len.value)
		mylzari_free_encoded(compressed)
		return ret;

def main2(args):
	import struct
	import os
	
	src = file(args[2], "rb").read()
	lzari = lzari_codec()
	out = file(args[3], "wb")
	start = os.times()
	if args[1] == "c":
		dest = lzari.encode(src)
		now = os.times()
		out.write(struct.pack("L", len(src)))
	else:
		dest = lzari.decode(src[4:],
				    struct.unpack("L", src[:4])[0])
		now = os.times()
	out.write(dest)
	out.close()
	print "time:", now[0] - start[0], now[1] - start[1], now[4] - start[4]


def _get_hotshot_lineinfo(filename):
	import hotshot.log
	log = hotshot.log.LogReader(filename)
	timings = {}
	for what, loc, tdelta in log:
		if what == hotshot.log.LINE:
			a = timings.get(loc)
			if a == None:
				timings[loc] = [1, tdelta]
			else:
				a[0] += 1
				a[1] += tdelta
	return timings.items()

def _dump_hotshot_lineinfo(log):
	a = sorted(_get_hotshot_lineinfo(log))
	total_count = sum((time[0]
			   for (loc, time) in a))
	total_time = sum((time[1]
			  for (loc, time) in a))
	for (loc, [count, time]) in a:
		print ("%8d %6.3f%%  %8d %6.3f%%"
		       % (time, time * 100.0 / total_time,
			  count, count * 100.0 / total_count)),
		print "%s:%d(%s)" % loc

def _dump_hotshot_lineinfo2(log):
	cur = None
	a = sorted(_get_hotshot_lineinfo(log))
	total_count = sum((time[0]
			   for (loc, time) in a))
	total_time = sum((time[1]
			  for (loc, time) in a))
	for ((filename, lineno, fn), [count, time]) in a:
		if cur != filename:
			if cur != None and f != None:
				for line in f:
					print line[:-1]
				f.close()
			try:
				f = file(filename, "r")
			except OSError:
				f = None
			cur = filename
			l = 0
			print "#", filename
		if f != None:
			while l < lineno:
				print f.readline()[:-1]
				l += 1
		print ("# %8d %6.3f%%  %8d %6.3f%%"
		       % (time, time * 100.0 / total_time,
			  count, count * 100.0 / total_count))
	if cur != None and f != None:
		for line in f:
			print line[:-1]
		f.close()
	
def main(args):
	import os
	
	if args[1] == "pc":
		import profile
		pr = profile.Profile()
		for i in range(5):
			print pr.calibrate(100000)
		return
	elif args[1] == "p":
		import profile
		ret = 0
		# profile.Profile.bias = 5.26e-6
		profile.runctx("ret = main2(args[1:])",
			       globals(), locals())
		return ret
	elif args[1].startswith("h"):
		import hotshot, hotshot.stats
		import warnings

		warnings.filterwarnings("ignore")
		tmp = os.tempnam()
		try:
			l = args[1].startswith("hl")
			p = hotshot.Profile(tmp, l)
			ret = p.runcall(main2, args[1:])
			p.close()
			p = None
			if l:
				if args[1] == "hl2":
					_dump_hotshot_lineinfo2(tmp)
				else:
					_dump_hotshot_lineinfo(tmp)
			else:
				hotshot.stats.load(tmp).print_stats()
		finally:
			try:
				os.remove(tmp)
			except OSError:
				pass
		return ret
			
	return main2(args)

if __name__ == '__main__':
	sys.exit(main(sys.argv))
	
