#
# ps2mc_dir.py
#
# By Ross Ridge
# Public Domain
#

"""Functions for working with PS2 memory card directory entries."""

_SCCS_ID = "@(#) mysc ps2mc_dir.py 1.4 12/10/04 19:11:08\n"

import struct
import time
import calendar

PS2MC_DIRENT_LENGTH = 512

DF_READ        = 0x0001
DF_WRITE       = 0x0002
DF_EXECUTE     = 0x0004
DF_RWX         = DF_READ | DF_WRITE | DF_EXECUTE
DF_PROTECTED   = 0x0008
DF_FILE        = 0x0010
DF_DIR         = 0x0020
DF_O_DCREAT    = 0x0040
DF_0080        = 0x0080
DF_0100        = 0x0100
DF_O_CREAT     = 0x0200
DF_0400        = 0x0400
DF_POCKETSTN   = 0x0800
DF_PSX         = 0x1000
DF_HIDDEN      = 0x2000
DF_4000        = 0x4000
DF_EXISTS      = 0x8000

def zero_terminate(s):
	"""Truncate a string at the first NUL ('\0') character, if any."""
	
	i = s.find('\0')
	if i == -1:
		return s
	return s[:i]

# mode, ???, length, created,
# fat_cluster, parent_entry, modified, attr,
# name
_dirent_fmt = "<HHL8sLL8sL28x448s"

# secs, mins, hours, mday, month, year
_tod_fmt = "<xBBBBBH"

#
# Use the new Struct object if available
# 
if hasattr(struct, "Struct"):
	_dirent_struct = struct.Struct(_dirent_fmt)
	_tod_struct = struct.Struct(_tod_fmt)

	def unpack_tod(s):
		return _tod_struct.unpack(s)
	
	def pack_tod(tod):
		return _tod_struct.pack(tod)
	
	def unpack_dirent(s):
		ent = _dirent_struct.unpack(s)
		ent = list(ent)
		ent[3] = _tod_struct.unpack(ent[3])
		ent[6] = _tod_struct.unpack(ent[6])
		ent[8] = zero_terminate(ent[8])
		return ent

	def pack_dirent(ent):
		ent = list(ent)
		ent[3] = _tod_struct.pack(*ent[3])
		ent[6] = _tod_struct.pack(*ent[6])
		return _dirent_struct.pack(*ent)
else:
	def unpack_tod(s):
		return struct.unpack(_tod_fmt, s)

	def pack_tod(tod):
		return struct.pack(_tod_fmt, tod)
	
	def unpack_dirent(s):
		# mode, ???, length, created,
		# fat_cluster, parent_entry, modified, attr,
		# name
		ent = struct.unpack(_dirent_fmt, s)
		ent = list(ent)
		ent[3] = struct.unpack(_tod_fmt, ent[3])
		ent[6] = struct.unpack(_tod_fmt, ent[6])
		ent[8] = zero_terminate(ent[8])
		return ent

	def pack_dirent(ent):
		ent = list(ent)
		ent[3] = struct.pack(_tod_fmt, *ent[3])
		ent[6] = struct.pack(_tod_fmt, *ent[6])
		return struct.pack(_dirent_fmt, *ent)

def time_to_tod(when):
	"""Convert a Python time value to a ToD tuple"""
	
	tm = time.gmtime(when + 9 * 3600)
	return (tm.tm_sec, tm.tm_min, tm.tm_hour,
		tm.tm_mday, tm.tm_mon, tm.tm_year)

def tod_to_time(tod):
	"""Convert a ToD tuple to a Python time value."""
	
	try:
		month = tod[4]
		if month == 0:
			month = 1
		return calendar.timegm((tod[5], month, tod[3],
					tod[2], tod[1], tod[0],
					None, None, 0)) - 9 * 3600
	except ValueError:
		return 0
		
def tod_now():
	"""Get the current time as a ToD tuple."""
	return time_to_tod(time.time())

def tod_from_file(filename):
	return time_to_tod(os.stat(filename).st_mtime)

def mode_is_file(mode):
	return (mode & (DF_FILE | DF_DIR | DF_EXISTS)) == (DF_FILE | DF_EXISTS)

def mode_is_dir(mode):
	return (mode & (DF_FILE | DF_DIR | DF_EXISTS)) == (DF_DIR | DF_EXISTS)

