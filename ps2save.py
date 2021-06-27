#
# ps2save.py
#
# By Ross Ridge
# Public Domain
# 
# A simple interface for working with various PS2 save file formats.
#

_SCCS_ID = "@(#) mysc ps2save.py 1.7 12/10/04 19:17:16\n"

import sys
import os
import string
import struct
import binascii
import array
import zlib

from round import div_round_up, round_up
from ps2mc_dir import *
from sjistab import shift_jis_normalize_table

try:
	import lzari
except ImportError:
	lzari = None

PS2SAVE_MAX_MAGIC = "Ps2PowerSave"
PS2SAVE_SPS_MAGIC = "\x0d\0\0\0SharkPortSave"
PS2SAVE_CBS_MAGIC = "CFU\0"
PS2SAVE_NPO_MAGIC = "nPort"

# This is the initial permutation state ("S") for the RC4 stream cipher
# algorithm used to encrpyt and decrypt Codebreaker saves.
PS2SAVE_CBS_RC4S = [0x5f, 0x1f, 0x85, 0x6f, 0x31, 0xaa, 0x3b, 0x18,
		    0x21, 0xb9, 0xce, 0x1c, 0x07, 0x4c, 0x9c, 0xb4,
		    0x81, 0xb8, 0xef, 0x98, 0x59, 0xae, 0xf9, 0x26,
		    0xe3, 0x80, 0xa3, 0x29, 0x2d, 0x73, 0x51, 0x62,
		    0x7c, 0x64, 0x46, 0xf4, 0x34, 0x1a, 0xf6, 0xe1,
		    0xba, 0x3a, 0x0d, 0x82, 0x79, 0x0a, 0x5c, 0x16,
		    0x71, 0x49, 0x8e, 0xac, 0x8c, 0x9f, 0x35, 0x19,
		    0x45, 0x94, 0x3f, 0x56, 0x0c, 0x91, 0x00, 0x0b,
		    0xd7, 0xb0, 0xdd, 0x39, 0x66, 0xa1, 0x76, 0x52,
		    0x13, 0x57, 0xf3, 0xbb, 0x4e, 0xe5, 0xdc, 0xf0,
		    0x65, 0x84, 0xb2, 0xd6, 0xdf, 0x15, 0x3c, 0x63,
		    0x1d, 0x89, 0x14, 0xbd, 0xd2, 0x36, 0xfe, 0xb1,
		    0xca, 0x8b, 0xa4, 0xc6, 0x9e, 0x67, 0x47, 0x37,
		    0x42, 0x6d, 0x6a, 0x03, 0x92, 0x70, 0x05, 0x7d,
		    0x96, 0x2f, 0x40, 0x90, 0xc4, 0xf1, 0x3e, 0x3d,
		    0x01, 0xf7, 0x68, 0x1e, 0xc3, 0xfc, 0x72, 0xb5,
		    0x54, 0xcf, 0xe7, 0x41, 0xe4, 0x4d, 0x83, 0x55,
		    0x12, 0x22, 0x09, 0x78, 0xfa, 0xde, 0xa7, 0x06,
		    0x08, 0x23, 0xbf, 0x0f, 0xcc, 0xc1, 0x97, 0x61,
		    0xc5, 0x4a, 0xe6, 0xa0, 0x11, 0xc2, 0xea, 0x74,
		    0x02, 0x87, 0xd5, 0xd1, 0x9d, 0xb7, 0x7e, 0x38,
		    0x60, 0x53, 0x95, 0x8d, 0x25, 0x77, 0x10, 0x5e,
		    0x9b, 0x7f, 0xd8, 0x6e, 0xda, 0xa2, 0x2e, 0x20,
		    0x4f, 0xcd, 0x8f, 0xcb, 0xbe, 0x5a, 0xe0, 0xed,
		    0x2c, 0x9a, 0xd4, 0xe2, 0xaf, 0xd0, 0xa9, 0xe8,
		    0xad, 0x7a, 0xbc, 0xa8, 0xf2, 0xee, 0xeb, 0xf5,
		    0xa6, 0x99, 0x28, 0x24, 0x6c, 0x2b, 0x75, 0x5d,
		    0xf8, 0xd3, 0x86, 0x17, 0xfb, 0xc0, 0x7b, 0xb3,
		    0x58, 0xdb, 0xc7, 0x4b, 0xff, 0x04, 0x50, 0xe9,
		    0x88, 0x69, 0xc9, 0x2a, 0xab, 0xfd, 0x5b, 0x1b,
		    0x8a, 0xd9, 0xec, 0x27, 0x44, 0x0e, 0x33, 0xc8,
		    0x6b, 0x93, 0x32, 0x48, 0xb6, 0x30, 0x43, 0xa5]

class error(Exception):
	"""Base for all exceptions specific to this module."""
	pass

class corrupt(error):
	"""Corrupt save file."""

	def __init__(self, msg, f = None):
		fn = None
		if f != None:
			fn = getattr(f, "name", None)
		self.filename = fn
		error.__init__(self, "Corrupt save file: " + msg)

class eof(corrupt):
	"""Save file is truncated."""

	def __init__(self, f = None):
		corrupt.__init__(self, "Unexpected EOF", f)

class subdir(corrupt):
	def __init__(self, f = None):
		corrupt.__init__(self, "Non-file in save file.", f)

#
# Table of graphically similar ASCII characters that can be used
# as substitutes for Unicode characters.
#
char_substs = {
	u'\u00a2': u"c",
	u'\u00b4': u"'",
	u'\u00d7': u"x",
	u'\u00f7': u"/",
	u'\u2010': u"-",
	u'\u2015': u"-",
	u'\u2018': u"'",
	u'\u2019': u"'",
	u'\u201c': u'"',
	u'\u201d': u'"',
	u'\u2032': u"'",
	u'\u2212': u"-",
	u'\u226a': u"<<",
	u'\u226b': u">>",
	u'\u2500': u"-",
	u'\u2501': u"-",
	u'\u2502': u"|",
	u'\u2503': u"|",
	u'\u250c': u"+",
	u'\u250f': u"+",
	u'\u2510': u"+",
	u'\u2513': u"+",
	u'\u2514': u"+",
	u'\u2517': u"+",
	u'\u2518': u"+",
	u'\u251b': u"+",
	u'\u251c': u"+",
	u'\u251d': u"+",
	u'\u2520': u"+",
	u'\u2523': u"+",
	u'\u2524': u"+",
	u'\u2525': u"+",
	u'\u2528': u"+",
	u'\u252b': u"+",
	u'\u252c': u"+",
	u'\u252f': u"+",
	u'\u2530': u"+",
	u'\u2533': u"+",
	u'\u2537': u"+",
	u'\u2538': u"+",
	u'\u253b': u"+",
	u'\u253c': u"+",
	u'\u253f': u"+",
	u'\u2542': u"+",
	u'\u254b': u"+",
	u'\u25a0': u"#",
	u'\u25a1': u"#",
	u'\u3001': u",",
	u'\u3002': u".",
	u'\u3003': u'"',
	u'\u3007': u'0',
	u'\u3008': u'<',
	u'\u3009': u'>',
	u'\u300a': u'<<',
	u'\u300b': u'>>',
	u'\u300a': u'<<',
	u'\u300b': u'>>',
	u'\u300c': u'[',
	u'\u300d': u']',
	u'\u300e': u'[',
	u'\u300f': u']',
	u'\u3010': u'[',
	u'\u3011': u']',
	u'\u3014': u'[',
	u'\u3015': u']',
	u'\u301c': u'~',
	u'\u30fc': u'-',
}

def shift_jis_conv(src, encoding = None):
	"""Convert Shift-JIS strings to a graphically similar representation.

	If encoding is "unicode" then a Unicode string is returned, otherwise
	a string in the encoding specified is returned.  If necessary,
	graphically similar characters are used to replace characters not
	exactly	representable in the desired encoding.
	"""
	
	if encoding == None:
		encoding = sys.getdefaultencoding()
	if encoding == "shift_jis":
		return src
	u = src.decode("shift_jis", "replace")
	if encoding == "unicode":
		return u
	a = []
	for uc in u:
		try:
			uc.encode(encoding)
			a.append(uc)
		except UnicodeError:
			for uc2 in shift_jis_normalize_table.get(uc, uc):
				a.append(char_substs.get(uc2, uc2))
	
	return u"".join(a).encode(encoding, "replace")

def rc4_crypt(s, t):
	"""RC4 encrypt/decrypt the string t using the permutation s.

	Returns a byte array."""
	
	s = array.array('B', s)
	t = array.array('B', t)
	j = 0
	for ii in range(len(t)):
		i = (ii + 1) % 256
		j = (j + s[i]) % 256
		(s[i], s[j]) = (s[j], s[i])
		t[ii] ^= s[(s[i] + s[j]) % 256]
	return t

# def sps_check(s):
# 	"""Calculate the checksum for a SharkPort save."""
#
# 	h = 0
# 	for c in array.array('B', s):
# 		h += c << (h % 24)
# 		h &= 0xFFFFFFFF
# 	return h

def unpack_icon_sys(s):
	"""Unpack an icon.sys file into a tuple."""
	
	# magic, title offset, ...
	# [14] title, normal icon, copy icon, del icon
	a = struct.unpack("<4s2xH4x"
			  "L" "16s16s16s16s" "16s16s16s" "16s16s16s" "16s"
			  "68s64s64s64s512x", s)
	a = list(a)
	for i in range(3, 7):
		a[i] = struct.unpack("<4L", a[i])
		a[i] = map(hex, a[i])
	for i in range(7, 14):
		a[i] = struct.unpack("<4f", a[i])
	a[14] = zero_terminate(a[14])
	a[15] = zero_terminate(a[15])
	a[16] = zero_terminate(a[16])
	a[17] = zero_terminate(a[17])
	return a

def icon_sys_title(icon_sys, encoding = None):
	"""Extract the two lines of the title stored in an icon.sys tuple."""
	
	offset = icon_sys[1]
	title = icon_sys[14]
	title2 = shift_jis_conv(title[offset:], encoding)
	title1 = shift_jis_conv(title[:offset], encoding)
	return (title1, title2)

def _read_fixed(f, n):
	"""Read a string of a fixed length from a file."""
	
	s = f.read(n)
	if len(s) != n:
		raise eof, f
	return s

def _read_long_string(f):
	"""Read a string prefixed with a 32-bit length from a file."""
	
	length = struct.unpack("<L", _read_fixed(f, 4))[0]
	return _read_fixed(f, length) 

class ps2_save_file(object):
	"""The state of a PlayStation 2 save file."""
	
	def __init__(self):
		self.file_ents = None
		self.file_data = None
		self.dirent = None
		self._defer_load_max = False

	def set_directory(self, ent, defer = False):
		self._defer_load_max = defer
		self._compressed = None
		self.file_ents = [None] * ent[2]
		self.file_data = [None] * ent[2]
		self.dirent = list(ent)

	def set_file(self, i, ent, data):
		self.file_ents[i] = ent
		self.file_data[i] = data

	def get_directory(self):
		return self.dirent

	def get_file(self, i):
		if self._defer_load_max:
			self._defer_load_max = False
			self._load_max_drive_2()
		return (self.file_ents[i], self.file_data[i])

	def __len__(self):
		return self.dirent[2]

	def __getitem__(self, index):
		return self.get_file(index)
	
	def get_icon_sys(self):
		for i in range(self.dirent[2]):
			(ent, data) = self.get_file(i)
			if ent[8] == "icon.sys" and len(data) >= 964:
				return unpack_icon_sys(data[:964])
		return None

	def load_ems(self, f):
		"""Load EMS (.psu) save files."""
		
		cluster_size = 1024

		dirent = unpack_dirent(_read_fixed(f, PS2MC_DIRENT_LENGTH))
		dotent = unpack_dirent(_read_fixed(f, PS2MC_DIRENT_LENGTH))
		dotdotent = unpack_dirent(_read_fixed(f, PS2MC_DIRENT_LENGTH))
		if (not mode_is_dir(dirent[0])
		    or not mode_is_dir(dotent[0])
		    or not mode_is_dir(dotdotent[0])
		    or dirent[2] < 2):
			raise corrupt, ("Not a EMS (.psu) save file.", f)

		dirent[2] -= 2
		self.set_directory(dirent)

		for i in range(dirent[2]):
			ent = unpack_dirent(_read_fixed(f,
							PS2MC_DIRENT_LENGTH))
			if not mode_is_file(ent[0]):
				raise subdir, f
			flen = ent[2]
			self.set_file(i, ent, _read_fixed(f, flen))
			_read_fixed(f, round_up(flen, cluster_size) - flen)


	def save_ems(self, f):
		cluster_size = 1024

		dirent = self.dirent[:]
		dirent[2] += 2
		f.write(pack_dirent(dirent))
		f.write(pack_dirent((DF_RWX | DF_DIR | DF_0400 | DF_EXISTS,
				     0, 0, dirent[3],
				     0, 0, dirent[3], 0, ".")))
		f.write(pack_dirent((DF_RWX | DF_DIR | DF_0400 | DF_EXISTS,
				     0, 0, dirent[3],
				     0, 0, dirent[3], 0, "..")))
				     
		for i in range(dirent[2] - 2):
			(ent, data) = self.get_file(i)
			f.write(pack_dirent(ent))
			if not mode_is_file(ent[0]):
				# print ent
				# print hex(ent[0])
				raise error, "Directory has a subdirectory."
			f.write(data)
			f.write("\0" * (round_up(len(data), cluster_size)
					- len(data)))
		f.flush()

	def _load_max_drive_2(self):
		(length, s) = self._compressed
		self._compressed = None
		
		if lzari == None:
			raise error, ("The lzari module is needed to "
				      " decompress MAX Drive saves.")
		s = lzari.decode(s, length,
				 "decompressing " + self.dirent[8] + ": ")
		dirlen = self.dirent[2]
		timestamp = self.dirent[3]
		off = 0
		for i in range(dirlen):
			if len(s) - off < 36:
				raise eof, f
			(l, name) = struct.unpack("<L32s", s[off : off + 36])
			name = zero_terminate(name)
			# print "%08x %08x %s" % (off, l, name)
			off += 36
			data = s[off : off + l]
			if len(data) != l:
				raise eof, f
			self.set_file(i,
				      (DF_RWX | DF_FILE | DF_0400 | DF_EXISTS,
				       0, l, timestamp, 0, 0, timestamp, 0,
				       name),
				      data)
			off += l
			off = round_up(off + 8, 16) - 8
		
	def load_max_drive(self, f, timestamp = None):
		s = f.read(0x5C)
		magic = None
		if len(s) == 0x5C:
			(magic, crc, dirname, iconsysname, clen, dirlen,
			 length) = struct.unpack("<12sL32s32sLLL", s)
		if magic != PS2SAVE_MAX_MAGIC:
			raise corrupt, ("Not a MAX Drive save file", f)
		if clen == length:
			# some saves have the uncompressed size here
			# instead of the compressed size
			s = f.read()
		else:
			s = _read_fixed(f, clen - 4)
		dirname = zero_terminate(dirname)
		if timestamp == None:
			timestamp = tod_now()
		self.set_directory((DF_RWX | DF_DIR | DF_0400 | DF_EXISTS,
				    0, dirlen, timestamp, 0, 0, timestamp, 0,
				    dirname),
				   True)
		self._compressed = (length, s)
		
	def save_max_drive(self, f):
		if lzari == None:
			raise error, ("The lzari module is needed to "
				      " decompress MAX Drive saves.")
		iconsysname = ""
		icon_sys = self.get_icon_sys()
		if icon_sys != None:
			title = icon_sys_title(icon_sys, "ascii")
			if len(title[0]) > 0 and title[0][-1] != ' ':
				iconsysname = title[0] + " " + title[1].strip()
			else:
				iconsysname = title[0] + title[1].rstrip()
		s = ""
		dirent = self.dirent
		for i in range(dirent[2]):
			(ent, data) = self.get_file(i)
			if not mode_is_file(ent[0]):
				raise error, "Non-file in save file."
			s += struct.pack("<L32s", ent[2], ent[8])
			s += data
			s += "\0" * (round_up(len(s) + 8, 16) - 8 - len(s))
		length = len(s)
		progress =  "compressing " + dirent[8] + ": "
		compressed = lzari.encode(s, progress)
		hdr = struct.pack("<12sL32s32sLLL", PS2SAVE_MAX_MAGIC,
				  0, dirent[8], iconsysname,
				  len(compressed) + 4, dirent[2], length)
		crc = binascii.crc32(hdr)
		crc = binascii.crc32(compressed, crc)
		f.write(struct.pack("<12sL32s32sLLL", PS2SAVE_MAX_MAGIC,
				    crc & 0xFFFFFFFF, dirent[8], iconsysname,
				    len(compressed) + 4, dirent[2], length))
		f.write(compressed)
		f.flush()

	def load_codebreaker(self, f):
		magic = f.read(4)
		if magic != PS2SAVE_CBS_MAGIC:
			raise corrupt, ("Not a Codebreaker save file.", f)
		(d04, hlen) = struct.unpack("<LL", _read_fixed(f, 8))
		if hlen < 92 + 32:
			raise corrupt, ("Header lengh too short.", f)
		(dlen, flen, dirname, created, modified, d44, d48, dirmode,
		 d50, d54, d58, title) \
		       = struct.unpack("<LL32s8s8sLLLLLL%ds" % (hlen - 92),
				       _read_fixed(f, hlen - 12))
		dirname = zero_terminate(dirname)
		created = unpack_tod(created)
		modified = unpack_tod(modified)
		title = zero_terminate(title)

		# These fields don't always seem to be set correctly.
		if not mode_is_dir(dirmode):
			dirmode = DF_RWX | DF_DIR | DF_0400
		if tod_to_time(created) == 0:
			created = tod_now()
		if tod_to_time(modified) == 0:
			modified = tod_now()

		# flen can either be the total length of the file,
		# or the length of compressed body of the file
		body = f.read(flen)
		clen = len(body)
		if clen != flen and clen != flen - hlen:
			raise eof, f
		body = rc4_crypt(PS2SAVE_CBS_RC4S, body)
		dcobj = zlib.decompressobj()
		body = dcobj.decompress(body, dlen)

		files = []
		while body != "":
			if len(body) < 64:
				raise eof, f
			header = struct.unpack("<8s8sLHHLL32s", body[:64])
			size = header[2]
			data = body[64 : 64 + size]
			if len(data) != size:
				raise eof, f
			body = body[64 + size:]
			files.append((header, data))
			
		self.set_directory((dirmode, 0, len(files), created, 0, 0,
				    modified, 0, dirname))
		for i in range(len(files)):
			(header, data) = files[i]
			(created, modified, size, mode, h06, h08, h0C, name) \
				= header
			name = zero_terminate(name)
			created = unpack_tod(created)
			modified = unpack_tod(modified)
			if not mode_is_file(mode):
				raise subdir, f
			if tod_to_time(created) == 0:
				created = tod_now()
			if tod_to_time(modified) == 0:
				modified = tod_now()
			self.set_file(i, (mode, 0, size, created, 0, 0,
					  modified, 0, name), data)

	def load_sharkport(self, f):
		magic = f.read(17)
		if magic != PS2SAVE_SPS_MAGIC:
			raise corrupt, ("Not a SharkPort/X-Port save file.", f)
		(savetype,) = struct.unpack("<L", _read_fixed(f, 4))
		dirname = _read_long_string(f)
		datestamp = _read_long_string(f)
		comment = _read_long_string(f)
		
		(flen,) = struct.unpack("<L", _read_fixed(f, 4))
		
		(hlen, dirname, dirlen, dirmode, created, modified) \
			= struct.unpack("<H64sL8xH2x8s8s", _read_fixed(f, 98))
		_read_fixed(f, hlen - 98)

		dirname = zero_terminate(dirname)
		created = unpack_tod(created)
		modified = unpack_tod(modified)

		# mode values are byte swapped
		dirmode = dirmode / 256 % 256 + dirmode % 256 * 256
		dirlen -= 2
		if not mode_is_dir(dirmode) or dirlen < 0:
			raise corrupt, ("Bad values in directory entry.", f)
		self.set_directory((dirmode, 0, dirlen, created, 0, 0,
				    modified, 0, dirname))

		for i in range(dirlen):
			(hlen, name, flen, mode, created, modified) \
			       = struct.unpack("<H64sL8xH2x8s8s",
					       _read_fixed(f, 98))
			if hlen < 98:
				raise corrupt, ("Header length too short.", f)
			_read_fixed(f, hlen - 98)
			name = zero_terminate(name)
			created = unpack_tod(created)
			modified = unpack_tod(modified)
			mode = mode / 256 % 256 + mode % 256 * 256
			if not mode_is_file(mode):
				raise subdir, f
			self.set_file(i, (mode, 0, flen, created, 0, 0,
					  modified, 0, name),
				      _read_fixed(f, flen))
			
		# ignore 4 byte checksum at the end
		
def detect_file_type(f):
	"""Detect the type of PS2 save file.

	The file-like object f should be positioned at the start of the file.
	"""
	
	hdr = f.read(PS2MC_DIRENT_LENGTH * 3)
	if hdr[:12] == PS2SAVE_MAX_MAGIC:
		return "max"
	if hdr[:17] == PS2SAVE_SPS_MAGIC:
		return "sps"
	if hdr[:4] == PS2SAVE_CBS_MAGIC:
		return "cbs"
	if hdr[:5] == PS2SAVE_NPO_MAGIC:
		return "npo"
	#
	# EMS (.psu) save files don't have a magic number.  Check to
	# see if it looks enough like one.
	#
	if len(hdr) != PS2MC_DIRENT_LENGTH * 3:
		return None
	dirent = unpack_dirent(hdr[:PS2MC_DIRENT_LENGTH])
	dotent = unpack_dirent(hdr[PS2MC_DIRENT_LENGTH
				   : PS2MC_DIRENT_LENGTH * 2])
	dotdotent = unpack_dirent(hdr[PS2MC_DIRENT_LENGTH * 2:])
	if (mode_is_dir(dirent[0]) and mode_is_dir(dotent[0])
	    and mode_is_dir(dotdotent[0]) and dirent[2] >= 2
	    and dotent[8] == "." and dotdotent[8] == ".."):
		return "psu"
	return None

#
# Set up tables of illegal and problematic characters in file names.
#
_bad_filename_chars = ("".join(map(chr, range(32)))
		       + "".join(map(chr, range(127, 256))))
_bad_filename_repl = "_" * len(_bad_filename_chars)

if os.name in ["nt", "os2", "ce"]:
	_bad_filename_chars += '<>:"/\\|'
	_bad_filename_repl +=  "()_'___"
	_bad_filename_chars2 = _bad_filename_chars + "?* "
	_bad_filename_repl2 = _bad_filename_repl +   "___"
else:
	_bad_filename_chars += "/"
	_bad_filename_repl += "_"
	_bad_filename_chars2 = _bad_filename_chars + "?*'&|:[<>] \\\""
	_bad_filename_repl2 = _bad_filename_repl +   "______(())___"

_filename_trans = string.maketrans(_bad_filename_chars, _bad_filename_repl);
_filename_trans2 = string.maketrans(_bad_filename_chars2, _bad_filename_repl2);

def fix_filename(filename):
	"""Replace illegal or problematic characters from a filename."""
	return filename.translate(_filename_trans)

def make_longname(dirname, sf):
	"""Return a string containing a verbose filename for a save file."""

	icon_sys = sf.get_icon_sys()
	title = ""
	if icon_sys != None:
		title = icon_sys_title(icon_sys, "ascii")
		title = title[0] + " " + title[1]
		title = " ".join(title.split())
	crc = binascii.crc32("")
	for (ent, data) in sf:
		crc = binascii.crc32(data, crc)
 	if len(dirname) >= 12 and (dirname[0:2] in ("BA", "BJ", "BE", "BK")):
		if dirname[2:6] == "DATA":
			title = ""
		else:
			#dirname = dirname[2:6] + dirname[7:12]
			dirname = dirname[2:12]

	return fix_filename("%s %s (%08X)"
			    % (dirname, title, crc & 0xFFFFFFFF))

