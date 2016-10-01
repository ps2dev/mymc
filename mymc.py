#
# mymc.py
#
# By Ross Ridge
# Public Domain
#

"""A utility for manipulating PS2 memory card images."""

_SCCS_ID = "@(#) mysc mymc.py 1.12 12/10/04 19:09:16\n"[:-1]

import sys
import os
import time
import optparse
import textwrap
import binascii
import string
from errno import EEXIST, EIO

import ps2mc
import ps2save
from ps2mc_dir import *
from round import *
import verbuild

class subopt_error(Exception):
	pass

io_error = ps2mc.io_error

if os.name == "nt":
	import codecs

	class file_wrap(object):
		""" wrap a file-like object with a new encoding attribute. """
		
		def __init__(self, f, encoding):
			object.__setattr__(self, "_f", f)
			object.__setattr__(self, "encoding", encoding)

		def __getattribute__(self, name):
			if name == "encoding":
				return object.__getattribute__(self, name)
			return getattr(object.__getattribute__(self, "_f"),
				       name)

		def __setattr__(self, name, value):
			if name == "encoding":
				raise TypeError, "readonly attribute"
			return setattr(object.__getattribute__(self, "_f"),
				       name, value)

	for name in ["stdin", "stdout", "stderr"]:
		f = getattr(sys, name)
		cur = getattr(f, "encoding", None)
		if cur == "ascii" or cur == None:
			f = file_wrap(f, "mbcs")
		else:
			try:
				codecs.lookup(cur)
			except LookupError:
				f = file_wrap(f, "mbcs")
		setattr(sys, name, f)


if os.name in ["nt", "os2", "ce"]:
	from glob import glob
else:
	# assume globing is done by the shell
	glob = lambda pattern: [pattern]


def glob_args(args, globfn):
	ret = []
	for arg in args:
		match = globfn(arg)
		if len(match) == 0:
			ret.append(arg)
		else:
			ret += match
	return ret
	      
def _copy(fout, fin):
	"""copy the contents of one file to another"""
	
	while True:
		s = fin.read(1024)
		if s == "":
			break
		fout.write(s)
	

def do_ls(cmd, mc, opts, args, opterr):
	mode_bits = "rwxpfdD81C+KPH4"

	if len(args) == 0:
		args = ["/"]

	out = sys.stdout
	args = glob_args(args, mc.glob)
	for dirname in args:
		dir = mc.dir_open(dirname)
		try:
			if len(args) > 1:
				sys.stdout.write("\n" + dirname + ":\n")
			for ent in dir:
				mode = ent[0]
				if (mode & DF_EXISTS) == 0:
					continue
				for bit in range(0, 15):
					if mode & (1 << bit):
						out.write(mode_bits[bit])
					else:
						out.write("-")
				if opts.creation_time:
					tod = ent[3]
				else:
					tod = ent[6]
				tm = time.localtime(tod_to_time(tod))
				out.write(" %7d %04d-%02d-%02d"
					  " %02d:%02d:%02d %s\n"
					  % (ent[2],
					     tm.tm_year, tm.tm_mon, tm.tm_mday,
					     tm.tm_hour, tm.tm_min, tm.tm_sec,
					     ent[8]))
		finally:
			dir.close()
			

def do_add(cmd, mc, opts,  args, opterr):
	if len(args) < 1:
		opterr("Filename required.")
	if opts.directory != None:
		mc.chdir(opts.directory)
	for src in glob_args(args, glob):
		f = open(src, "rb")
		dest = os.path.basename(src)
		out = mc.open(dest, "wb")
		_copy(out, f)
		out.close()
		f.close()
		
def do_extract(cmd, mc, opts, args, opterr):
	if len(args) < 1:
		opterr("Filename required.")

	if opts.directory != None:
		mc.chdir(opts.directory)

	close_out = False
	out = None
	if opts.output != None:
		if opts.use_stdout:
			opterr("The -o and -p options are mutually exclusive.")
		dont_close_out = True
		out = file(opts.output, "wb")
	elif opts.use_stdout:
		out = sys.stdout

	try:
		for filename in glob_args(args, mc.glob):
			f = mc.open(filename, "rb")
			try:
				if out != None:
					_copy(out, f)
					continue
				a = filename.split("/")
				o = file(a[-1], "wb")
				try:
					_copy(o, f)
				finally:
					o.close()
			finally:
				f.close()
	finally:
		if close_out:
			out.close()

def do_mkdir(cmd, mc, opts, args, opterr):
	if len(args) < 1:
		opterr("Directory required.")
		
	for filename in args:
		mc.mkdir(filename)

def do_remove(cmd, mc, opts, args, opterr):
	if len(args) < 1:
		opterr("Filename required.")
		
	for filename in args:
		mc.remove(filename)

def do_import(cmd, mc, opts, args, opterr):
	if len(args) < 1:
		opterr("Filename required.")

	args = glob_args(args, glob)
	if opts.directory != None and len(args) > 1:
		opterr("The -d option can only be used with a"
		       "single savefile.")
		
	for filename in args:
		sf = ps2save.ps2_save_file()
		f = file(filename, "rb")
		try:
			ftype = ps2save.detect_file_type(f)
			f.seek(0)
			if ftype == "max":
				sf.load_max_drive(f)
			elif ftype == "psu":
				sf.load_ems(f)
			elif ftype == "cbs":
				sf.load_codebreaker(f)
			elif ftype == "sps":
				sf.load_sharkport(f)
			elif ftype == "npo":
				raise io_error, (EIO, "nPort saves"
						 " are not supported.",
						 filename)
			else:
				raise io_error, (EIO, "Save file format not"
						 " recognized", filename)
		finally:
			f.close()
		dirname = opts.directory
		if dirname == None:
			dirname = sf.get_directory()[8]
		print "Importing", filename, "to", dirname
		if not mc.import_save_file(sf, opts.ignore_existing,
						opts.directory):
			print (filename + ": already in memory card image,"
			       " ignored.")

#re_num = re.compile("[0-9]+")

def do_export(cmd, mc, opts, args, opterr):
	if len(args) < 1:
		opterr("Directory name required")

	if opts.overwrite_existing and opts.ignore_existing:
		opterr("The -i and -f options are mutually exclusive.")
		
	args = glob_args(args, mc.glob)
	if opts.output_file != None:
		if len(args) > 1:
			opterr("Only one directory can be exported"
			       " when the -o option is used.")
		if opts.longnames:
			opterr("The -o and -l options are mutually exclusive.")

	if opts.directory != None:
		os.chdir(opts.directory)
		
	for dirname in args:
		sf = mc.export_save_file(dirname)
		filename = opts.output_file
		if opts.longnames:
			filename = (ps2save.make_longname(dirname, sf)
				    + "." + opts.type)
		if filename == None:
			filename = dirname + "." + opts.type
				
		if not opts.overwrite_existing:
			exists = True
			try:
				open(filename, "rb").close()
			except EnvironmentError:
				exists = False
			if exists:
				if opts.ignore_existing:
					continue
				raise io_error(EEXIST, "File exists", filename)
			
		f = file(filename, "wb")
		try:
			print "Exporing", dirname, "to", filename
			
			if opts.type == "max":
				sf.save_max_drive(f)
			else:
				sf.save_ems(f)
		finally:
			f.close()

def do_delete(cmd, mc, opts, args, opterr):
	if len(args) < 1:
		opterr("Directory required.")

	for dirname in args:
		mc.rmdir(dirname)
	
def do_setmode(cmd, mc, opts, args, opterr):
	set_mask = 0
	clear_mask = ~0
	for (opt, bit) in [(opts.read, DF_READ),
			   (opts.write, DF_WRITE),
			   (opts.execute, DF_EXECUTE),
			   (opts.protected, DF_PROTECTED),
			   (opts.psx, DF_PSX),
			   (opts.pocketstation, DF_POCKETSTN),
			   (opts.hidden, DF_HIDDEN)]:
		if opt != None:
			if opt:
				set_mask |= bit
			else:
				clear_mask ^= bit

	value = opts.hex_value
	if set_mask == 0 and clear_mask == ~0:
		if value == None:
			opterr("At least one option must be given.")
		if value.startswith("0x") or value.startswith("0X"):
			value = int(value[2:], 16)
		else:
			value = int(value, 16)
	else:
		if value != None:
			opterr("The -X option can't be combined with"
			       " other options.")

	for arg in glob_args(args, mc.glob):
		ent = mc.get_dirent(arg)
		if value == None:
			ent[0] = (ent[0] & clear_mask) | set_mask
			# print "new %04x" % ent[0]
		else:
			ent[0] = value
		mc.set_dirent(arg, ent)

def _get_ps2_title(mc, enc):
	s = mc.get_icon_sys(".");
	if s == None:
		return None
	a = ps2save.unpack_icon_sys(s)
	return ps2save.icon_sys_title(a, enc)

def _get_psx_title(mc, savename, enc):
	mode = mc.get_mode(savename)
	if mode == None or not mode_is_file(mode):
		return None
	f = mc.open(savename)
	s = f.read(128)
	if len(s) != 128:
		return None
	(magic, icon, blocks, title) = struct.unpack("<2sBB64s28x32x", s)
	if magic != "SC":
		return None
	return [ps2save.shift_jis_conv(zero_terminate(title), enc), ""]

def do_dir(cmd, mc, opts, args, opterr):
	if len(args) != 0:
		opterr("Incorrect number of arguments.")
	f = None
	dir = mc.dir_open("/")
	try:
		for ent in list(dir)[2:]:
			dirmode = ent[0]
			if not mode_is_dir(dirmode):
				continue
			dirname = "/" + ent[8]
			mc.chdir(dirname)
			length = mc.dir_size(".");
			enc = getattr(sys.stdout, "encoding", None)
			if dirmode & DF_PSX:
				title = _get_psx_title(mc, ent[8], enc)
			else:
				title = _get_ps2_title(mc, enc)
			if title == None:
				title = ["Corrupt", ""]
			protection = dirmode & (DF_PROTECTED | DF_WRITE)
			if protection == 0:
				protection = "Delete Protected"
			elif protection == DF_WRITE:
				protection = "Not Protected"
			elif protection == DF_PROTECTED:
				protection = "Copy & Delete Protected"
			else:
				protection = "Copy Protected"

			type = None
			if dirmode & DF_PSX:
				type = "PlayStation"
				if dirmode & DF_POCKETSTN:
					type = "PocketStation"
			if type != None:
				protection = type
				
			print "%-32s %s" % (ent[8], title[0])
			print ("%4dKB %-25s %s"
			       % (length / 1024, protection, title[1]))
			print
	finally:
		if f != None:
			f.close()
		dir.close()
		
	free = mc.get_free_space() / 1024
	if free > 999999:
		free = "%d,%03d,%03d" % (free / 1000000, free / 1000 % 1000,
					 free % 1000)
	elif free > 999:
		free = "%d,%03d" % (free / 1000, free % 1000)
	else:
		free = "%d" % free

	print free + " KB Free"

def do_df(cmd, mc, opts, args, opterr):
	if len(args) != 0:
		opterr("Incorrect number of arguments.")
	print mc.f.name + ":", mc.get_free_space(), "bytes free."

def do_check(cmd, mc, opts, args, opterr):
	if len(args) != 0:
		opterr("Incorrect number of arguments.")
	if mc.check():
		print "No errors found."
		return 0
	return 1
	
def do_format(cmd, mcname, opts, args, opterr):
	if len(args) != 0:
		opterr("Incorrect number of arguments.")
	pages_per_card = ps2mc.PS2MC_STANDARD_PAGES_PER_CARD
	if opts.clusters != None:
		pages_per_cluster = (ps2mc.PS2MC_CLUSTER_SIZE
				     / ps2mc.PS2MC_STANDARD_PAGE_SIZE)
		pages_per_card = opts.clusters * pages_per_cluster
	params = (not opts.no_ecc,
		  ps2mc.PS2MC_STANDARD_PAGE_SIZE,
		  ps2mc.PS2MC_STANDARD_PAGES_PER_ERASE_BLOCK,
		  pages_per_card)

	if not opts.overwrite_existing:
		exists = True
		try:
			file(mcname, "rb").close()
		except EnvironmentError:
			exists = False
		if exists:
			raise io_error, (EEXIST, "file exists", mcname)

	f = file(mcname, "w+b")
	try:
		ps2mc.ps2mc(f, True, params).close()
	finally:
		f.close()

def do_gui(cmd, mcname, opts, args, opterr):
	if len(args) != 0:
		opterr("Incorrect number of arguments.")

	try:
		import gui
	except ImportError:
		write_error(None, "GUI not available")
		return 1

	gui.run(mcname)
	return 0

def do_create_pad(cmd, mc, opts, args, opterr):
	length = mc.clusters_per_card
	if len(args) > 1:
		length = int(args[1])
	pad = "\0" * mc.cluster_size
	f = mc.open(args[0], "wb")
	try:
		for i in xrange(length):
			f.write(pad)
	finally:
		f.close()
	
		
def do_frob(cmd, mc, opts, args, opterr):
	mc.write_superblock()

_trans = string.maketrans("".join(map(chr, range(32))), " " * 32)

def _print_bin(base, s):
	for off in range(0, len(s), 16):
		print "%04X" % (base + off),
		a = s[off : off + 16]
		for b in a:
			print "%02X" % ord(b),
		print "", a.translate(_trans)
	
def _print_erase_block(mc, n):
	ppb = mc.pages_per_erase_block
	base = n * ppb
	for i in range(ppb):
		s = mc.read_page(base + i)
		_print_bin(i * mc.page_size, s)
		print
		
def do_print_good_blocks(cmd, mc, opts, args, opterr):
	print "good_block2:"
	_print_erase_block(mc, mc.good_block2)
	print "good_block1:"
	_print_erase_block(mc, mc.good_block1)

def do_ecc_check(cmd, mc, opts, args, opterr):
	for i in range(mc.clusters_per_card * mc.pages_per_cluster):
		try:
			mc.read_page(i)
		except ps2mc.ecc_error:
			print "bad: %05x" % i

opt = optparse.make_option

#
# Each value in the dictionary is a tuple consisting of:
#    - function implementing the command
#    - mode to use to open the ps2 save file
#    - help description of the command
#    - list of options supported by the command
#
cmd_table = {
	"ls": (do_ls, "rb",
	       "[directory ...]",
	       "List the contents of a directory.",
	       [opt("-c", "--creation-time", action="store_true",
		    help = "Display creation times.")]),
	"extract": (do_extract, "rb",
		    "filename ...",
		    "Extract files from the memory card.",
		    [opt("-o", "--output", metavar = "FILE",
			 help = 'Extract file to "FILE".'),
		     opt("-d", "--directory", 
			 help = 'Extract files from "DIRECTORY".'),
		     opt("-p", "--use-stdout", action="store_true",
			 help = "Extract files to standard output.")]),
	"add": (do_add, "r+b",
		"filename ...",
		"Add files to the memory card.",
		[opt("-d", "--directory", 
		     help = 'Add files to "directory".')]),
	"mkdir": (do_mkdir, "r+b",
		  "directory ...",
		  "Make directories.",
		  []),
	"remove": (do_remove, "r+b",
		   "filename ...",
		   "Remove files and directories.",
		   []),
	"import": (do_import, "r+b",
		   "savefile ...",
		   "Import save files into the memory card.",
		   [opt("-i", "--ignore-existing", action="store_true",
			help = ("Ignore files that already exist"
				"on the image.")),
		    opt("-d", "--directory", metavar="DEST",
			help = 'Import to "DEST".')]),
	"export": (do_export, "rb",
		   "directory ...",
		   "Export save files from the memory card.",
		   [opt("-f", "--overwrite-existing", action = "store_true",
			help = "Overwrite any save files already exported."),
		    opt("-i", "--ignore-existing", action = "store_true",
			help = "Ingore any save files already exported."),
		    opt("-o", "--output-file", metavar = "filename",
			help = 'Use "filename" as the name of the save file.'),
		    opt("-d", "--directory", metavar = "directory",
			help = 'Export save files to "directory".'),
		    opt("-l", "--longnames", action = "store_true",
			help = ("Generate longer, more descriptive,"
				" filenames.")),
		    opt("-p", "--ems", action = "store_const",
			dest = "type", const = "psu", default = "psu",
			help = "Use the EMS .psu save file format. [default]"),
		    opt("-m", "--max-drive", action = "store_const",
			dest = "type", const = "max",
			help = "Use the MAX Drive save file format.")]),
	"delete": (do_delete, "r+b",
		   "dirname ...",
		   "Recursively delete a directory (save file).",
		   []),
	"set": (do_setmode, "r+b",
		"filename ...",
		"Set mode flags on files and directories",
		[opt("-p", "--protected", action="store_true",
		     help = "Set copy protected flag"),
		 opt("-P", "--psx", action="store_true",
		     help = "Set PSX flag"),
		 opt("-K", "--pocketstation", action="store_true",
		     help = "Set PocketStation flag"),
		 opt("-H", "--hidden", action="store_true",
		     help = "Set hidden flag"),
		 opt("-r", "--read", action="store_true",
		     help = "Set read allowed flag"),
		 opt("-w", "--write", action="store_true",
		     help = "Set write allowed flag"),
		 opt("-x", "--execute", action="store_true",
		     help = "Set executable flag"),
		 opt("-X", "--hex-value", metavar="mode",
		     help = 'Set mode to "mode".')]),
	"clear": (do_setmode, "r+b",
		"filename ...",
		"Clear mode flags on files and directories",
		[opt("-p", "--protected", action="store_false",
		     help = "Clear copy protected flag"),
		 opt("-P", "--psx", action="store_false",
		     help = "Clear PSX flag"),
		 opt("-K", "--pocketstation", action="store_false",
		     help = "Clear PocketStation flag"),
		 opt("-H", "--hidden", action="store_false",
		     help = "Clear hidden flag"),
		 opt("-r", "--read", action="store_false",
		     help = "Clear read allowed flag"),
		 opt("-w", "--write", action="store_false",
		     help = "Clear write allowed flag"),
		 opt("-x", "--execute", action="store_false",
		     help = "Clear executable flag"),
		 opt("-X", dest="hex_value", default=None,
		     help = optparse.SUPPRESS_HELP)]),
	"dir": (do_dir, "rb",
		None,
		"Display save file information.",
		[]),
	"df": (do_df, "rb",
	       None,
	       "Display the amount free space.",
	       []),
	"check": (do_check, "rb",
		  "",
		  "Check for file system errors.",
		  []),
	"format": (do_format, None,
		   "",
		   "Creates a new memory card image.",
		   [opt("-c", "--clusters", type="int",
			help = "Size in clusters of the memory card."),
		    opt("-f", "--overwrite-existing", action="store_true",
			help = "Overwrite any existing file"),
		    opt("-e", "--no-ecc", action="store_true",
			help = "Create an image without ECC")]),
	"gui": (do_gui, None,
		"",
		"Starts the graphical user interface.",
		[]),
}

#
# secret commands for debugging purposes.
# 
debug_cmd_table = {
	"frob": (do_frob, "r+b",
		 "",
		 None,
		 []),
	"print_good_blocks": (do_print_good_blocks, "rb",
			      "",
			      None,
			      []),
	"ecc_check": (do_ecc_check, "rb",
		      "",
		      None,
		      []),
	"create_pad": (do_create_pad, "r+b",
		       "",
		       None,
		       [])
}

del opt		# clean up name space


def write_error(filename, msg):
	if filename == None:
		sys.stderr.write(msg + "\n")
	else:
		sys.stderr.write(filename + ": " + msg + "\n")

class suboption_parser(optparse.OptionParser):
	def exit(self, status = 0, msg = None):
		if msg:
			sys.stderr.write(msg)
		raise subopt_error, status

class my_help_formatter(optparse.IndentedHelpFormatter):
	"""A better formatter for optparser's help message"""
	
	def format_description(self, description):
		if not description:
			return ""
		desc_width = self.width - self.current_indent
		indent = " " * self.current_indent
		lines = []
		for line in description.split('\n'):
			ii = indent
			si = indent
			if line.startswith("\t"):
				line = line[1:]
				ii = indent + " " * 4
				si = ii + " " * line.find(":") + 2
			line = textwrap.fill(line, desc_width,
					     initial_indent = ii,
					     subsequent_indent = si)
			lines.append(line)
		return "\n".join(lines) + "\n"

def main():
	prog = sys.argv[0].decode(sys.getdefaultencoding(), "replace")
	usage = "usage: %prog [-ih] memcard.ps2 command [...]"
	description = ("Manipulate PS2 memory card images.\n\n"
		       "Supported commands: ")
	for cmd in sorted(cmd_table.keys()):
		description += "\n   " + cmd + ": " + cmd_table[cmd][3]
		
	version = ("mymc "
		   + verbuild.MYMC_VERSION_MAJOR
		   + "." + verbuild.MYMC_VERSION_BUILD
		   + "   (" + _SCCS_ID + ")")

	optparser = optparse.OptionParser(prog = prog, usage = usage,
					  description = description,
			 		  version = version,
					  formatter = my_help_formatter())
	optparser.add_option("-D", dest = "debug", action = "store_true",
			     default = False, help = optparse.SUPPRESS_HELP)
	optparser.add_option("-i", "--ignore-ecc", action = "store_true",
			     help = "Ignore ECC errors while reading.")
			     
	optparser.disable_interspersed_args()
	(opts, args) = optparser.parse_args()

	if len(args) == 0:
		try:
			import gui
		except ImportError:
			gui = None
		if gui != None:
			gui.run()
			sys.exit(0)

	if len(args) < 2:
		optparser.error("Incorrect number of arguments.")

	if opts.debug:
		cmd_table.update(debug_cmd_table)
	cmd = args[1]
	if cmd not in cmd_table:
		optparser.error('Command "%s" not recognized.' % cmd)
	(fn, mode, usage_args, description, optlist) = cmd_table[cmd]

	usage = "%prog"
	if len(optlist) > 0:
		usage += " [options]"
	if usage_args != None:
		usage += " " + usage_args
	subprog = prog + " memcard.ps2 " + cmd
	subopt_parser = suboption_parser(prog = subprog, usage = usage,
					 description = description,
					 option_list = optlist)
	subopt_parser.disable_interspersed_args()
	
	f = None
	mc = None
	ret = 0
	mcname = args[0]

	try:
		(subopts, subargs) = subopt_parser.parse_args(args[2:])
		try:
			if mode == None:
				ret = fn(cmd, mcname, subopts, subargs,
					 subopt_parser.error)
			else:
				f = file(mcname, mode)
				mc = ps2mc.ps2mc(f, opts.ignore_ecc)
				ret = fn(cmd, mc, subopts, subargs,
					 subopt_parser.error)
		finally:
			if mc != None:
				mc.close()
			if f != None:
				# print "f.close()"
				f.close()

	except EnvironmentError, value:
		if getattr(value, "filename", None) != None:
			write_error(value.filename, value.strerror)
			ret = 1
		elif getattr(value, "strerror", None) != None:
			write_error(mcname, value.strerror)
			ret = 1
		else:		
			# something weird
			raise
		if opts.debug:
			raise

	except subopt_error, (ret,):
		pass
	
	except (ps2mc.error, ps2save.error), value:
		fn = getattr(value, "filename", None)
		if fn == None:
			fn = mcname
		write_error(fn, str(value))
		if opts.debug:
			raise
		ret = 1

	if ret == None:
		ret = 0

	return ret

sys.exit(main())

