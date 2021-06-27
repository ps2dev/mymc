#
# gui.py
#
# By Ross Ridge
# Public Domain
#

"""Graphical user-interface for mymc."""

_SCCS_ID = "@(#) mymc gui.py 1.4 12/10/04 18:51:51\n"

import os
import sys
import struct
import cStringIO
import time

# Work around a problem with mixing wx and py2exe
if os.name == "nt" and hasattr(sys, "setdefaultencoding"):
	sys.setdefaultencoding("mbcs")
import wx

import ps2mc
import ps2save
import guires

try:
	import ctypes
	import mymcsup
	D3DXVECTOR3 = mymcsup.D3DXVECTOR3
	D3DXVECTOR4 = mymcsup.D3DXVECTOR4
	D3DXVECTOR4_ARRAY3 = mymcsup.D3DXVECTOR4_ARRAY3

	def mkvec4arr3(l):
		return D3DXVECTOR4_ARRAY3(*[D3DXVECTOR4(*vec)
					    for vec in l])
except ImportError:
	mymcsup = None

lighting_none = {"lighting": False,
		 "vertex_diffuse": False,
		 "alt_lighting": False,
		 "light_dirs": [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
		 "light_colours": [[0, 0, 0, 0], [0, 0, 0, 0],
				   [0, 0, 0, 0]],
		 "ambient": [0, 0, 0, 0]}

lighting_diffuse = {"lighting": False,
		    "vertex_diffuse": True,
		    "alt_lighting": False,
		    "light_dirs": [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
		    "light_colours": [[0, 0, 0, 0], [0, 0, 0, 0],
				      [0, 0, 0, 0]],
		    "ambient": [0, 0, 0, 0]}

lighting_icon = {"lighting": True,
		 "vertex_diffuse": True,
		 "alt_lighting": False,
		 "light_dirs": [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
		 "light_colours": [[0, 0, 0, 0], [0, 0, 0, 0],
				   [0, 0, 0, 0]],
		 "ambient": [0, 0, 0, 0]}

lighting_alternate = {"lighting": True,
		      "vertex_diffuse": True,
		      "alt_lighting": True,
		      "light_dirs": [[1, -1, 2, 0],
				     [-1, 1, -2, 0],
				     [0, 1, 0, 0]],
		      "light_colours": [[1, 1, 1, 1],
					[1, 1, 1, 1],
					[0.7, 0.7, 0.7, 1]],
		      "ambient": [0.5, 0.5, 0.5, 1]}

lighting_alternate2 = {"lighting": True,
		       "vertex_diffuse": False,
		       "alt_lighting": True,
		       "light_dirs": [[1, -1, 2, 0],
				      [-1, 1, -2, 0],
				      [0, 4, 1, 0]],
		       "light_colours": [[0.7, 0.7, 0.7, 1],
					 [0.7, 0.7, 0.7, 1],
					 [0.2, 0.2, 0.2, 1]],
		       "ambient": [0.3, 0.3, 0.3, 1]}

camera_default = [0, 4, -8]
camera_high = [0, 7, -6]
camera_near = [0, 3, -6]
camera_flat = [0, 2, -7.5]

def get_dialog_units(win):
	return win.ConvertDialogPointToPixels((1, 1))[0]

def single_title(title):
	"""Convert the two parts of an icon.sys title into one string."""
	
	title = title[0] + " " + title[1]
	return u" ".join(title.split())

def _get_icon_resource_as_images(name):
	ico = guires.resources[name]
	images = []
	f = cStringIO.StringIO(ico)
	count = struct.unpack("<HHH", ico[0:6])[2]
	# count = wx.Image_GetImageCount(f, wx.BITMAP_TYPE_ICO)
	for i in range(count):
		f.seek(0)
		images.append(wx.ImageFromStream(f, wx.BITMAP_TYPE_ICO, i))
	return images
	
def get_icon_resource(name):
	"""Convert a Window ICO contained in a string to an IconBundle."""

	bundle = wx.IconBundle()
	for img in _get_icon_resource_as_images(name):
		bmp = wx.BitmapFromImage(img)
		icon = wx.IconFromBitmap(bmp)
		bundle.AddIcon(icon)
	return bundle

def get_icon_resource_bmp(name, size):
	"""Get an icon resource as a Bitmap.

	Tries to find the closest matching size if no exact match exists."""
	
	best = None
	best_size = (0, 0)
	for img in _get_icon_resource_as_images(name):
		sz = (img.GetWidth(), img.GetHeight())
		if sz == size:
			return wx.BitmapFromImage(img)
		if sz[0] >= size[0] and sz[1] >= size[1]:
			if ((best_size[0] < size[0] or best_size[1] < size[1])
			    or sz[0] * sz[1] < best_size[0] * best_size[1]):
				best = img
				best_size = sz
		elif sz[0] * sz[1] > best_size[0] * best_size[1]:
			best = img
			best_size = sz
	img = best.Rescale(size[0], size[1], wx.IMAGE_QUALITY_HIGH)
	return wx.BitmapFromImage(img)


class dirlist_control(wx.ListCtrl):
	"""Lists all the save files in a memory card image."""
	
	def __init__(self, parent, evt_focus, evt_select, config):
		self.config = config
		self.selected = set()
		self.evt_select = evt_select
		wx.ListCtrl.__init__(self, parent, wx.ID_ANY,
				     style = wx.LC_REPORT)
		wx.EVT_LIST_COL_CLICK(self, -1, self.evt_col_click)
		wx.EVT_LIST_ITEM_FOCUSED(self, -1, evt_focus)
		wx.EVT_LIST_ITEM_SELECTED(self, -1, self.evt_item_selected)
		wx.EVT_LIST_ITEM_DESELECTED(self, -1, self.evt_item_deselected)

	def _update_dirtable(self, mc, dir):
		self.dirtable = table = []
		enc = "unicode"
		if self.config.get_ascii():
			enc = "ascii"
		for ent in dir:
			if not ps2mc.mode_is_dir(ent[0]):
				continue
			dirname = "/" + ent[8]
			s = mc.get_icon_sys(dirname)
			if s == None:
				continue
			a = ps2save.unpack_icon_sys(s)
			size = mc.dir_size(dirname)
			title = ps2save.icon_sys_title(a, encoding = enc)
			table.append((ent, s, size, title))
		
	def update_dirtable(self, mc):
		self.dirtable = []
		if mc == None:
			return
		dir = mc.dir_open("/")
		try:
			self._update_dirtable(mc, dir)
		finally:
			dir.close()
			
	def cmp_dir_name(self, i1, i2):
		return self.dirtable[i1][0][8] > self.dirtable[i2][0][8]

	def cmp_dir_title(self, i1, i2):
		return self.dirtable[i1][3] > self.dirtable[i2][3]

	def cmp_dir_size(self, i1, i2):
		return self.dirtable[i1][2] > self.dirtable[i2][2]

	def cmp_dir_modified(self, i1, i2):
		m1 = list(self.dirtable[i1][0][6])
		m2 = list(self.dirtable[i2][0][6])
		m1.reverse()
		m2.reverse()
		return m1 > m2
	
	def evt_col_click(self, event):
		col = event.m_col
		if col == 0:
			cmp = self.cmp_dir_name
		elif col == 1:
			cmp = self.cmp_dir_size
		elif col == 2:
			cmp = self.cmp_dir_modified
		elif col == 3:
			cmp = self.cmp_dir_title
		self.SortItems(cmp)
		return

	def evt_item_selected(self, event):
		self.selected.add(event.GetData())
		self.evt_select(event)
		
	def evt_item_deselected(self, event):
		self.selected.discard(event.GetData())
		self.evt_select(event)
		
	def update(self, mc):
		"""Update the ListCtrl according to the contents of the
		   memory card image."""
		
		self.ClearAll()
		self.selected = set()
		self.InsertColumn(0, "Directory")
		self.InsertColumn(1, "Size")
		self.InsertColumn(2, "Modified")
		self.InsertColumn(3, "Description")
		li = self.GetColumn(1)
		li.SetAlign(wx.LIST_FORMAT_RIGHT)
		li.SetText("Size")
		self.SetColumn(1, li)
		
		self.update_dirtable(mc)
		
		empty = len(self.dirtable) == 0
		self.Enable(not empty)
		if empty:
			return
		
		for (i, a) in enumerate(self.dirtable):
			(ent, icon_sys, size, title) = a
			li = self.InsertStringItem(i, ent[8])
			self.SetStringItem(li, 1, "%dK" % (size / 1024))
			m = ent[6]
			m = ("%04d-%02d-%02d %02d:%02d"
			     % (m[5], m[4], m[3], m[2], m[1]))
			self.SetStringItem(li, 2, m)
			self.SetStringItem(li, 3, single_title(title))
			self.SetItemData(li, i)

		du = get_dialog_units(self)
		for i in range(4):
			self.SetColumnWidth(i, wx.LIST_AUTOSIZE)
			self.SetColumnWidth(i, self.GetColumnWidth(i) + du)
		self.SortItems(self.cmp_dir_name)


class icon_window(wx.Window):
	"""Displays a save file's 3D icon.  Windows only.
	
	The rendering of the 3D icon is handled by C++ code in the
	mymcsup DLL which subclasses this window.  This class mainly
	handles configuration options that affect how the 3D icon is
	displayed.
	"""
	
	ID_CMD_ANIMATE        = 201
	ID_CMD_LIGHT_NONE     = 202
	ID_CMD_LIGHT_ICON     = 203
	ID_CMD_LIGHT_ALT1     = 204
	ID_CMD_LIGHT_ALT2     = 205
	ID_CMD_CAMERA_FLAT    = 206
	ID_CMD_CAMERA_DEFAULT = 207
	ID_CMD_CAMERA_NEAR    = 209
	ID_CMD_CAMERA_HIGH    = 210

	light_options = {ID_CMD_LIGHT_NONE: lighting_none,
			 ID_CMD_LIGHT_ICON: lighting_icon,
			 ID_CMD_LIGHT_ALT1: lighting_alternate,
			 ID_CMD_LIGHT_ALT2: lighting_alternate2}

	camera_options = {ID_CMD_CAMERA_FLAT: camera_flat,
			  ID_CMD_CAMERA_DEFAULT: camera_default,
			  ID_CMD_CAMERA_NEAR: camera_near,
			  ID_CMD_CAMERA_HIGH: camera_high}

	def append_menu_options(self, win, menu):
		menu.AppendCheckItem(icon_window.ID_CMD_ANIMATE,
				     "Animate Icons")
		menu.AppendSeparator()
		menu.AppendRadioItem(icon_window.ID_CMD_LIGHT_NONE,
				     "Lighting Off")
		menu.AppendRadioItem(icon_window.ID_CMD_LIGHT_ICON,
				     "Icon Lighting")
		menu.AppendRadioItem(icon_window.ID_CMD_LIGHT_ALT1,
				     "Alternate Lighting")
		menu.AppendRadioItem(icon_window.ID_CMD_LIGHT_ALT2,
				     "Alternate Lighting 2")
		menu.AppendSeparator()
		menu.AppendRadioItem(icon_window.ID_CMD_CAMERA_FLAT,
				     "Camera Flat")
		menu.AppendRadioItem(icon_window.ID_CMD_CAMERA_DEFAULT,
				     "Camera Default")
		menu.AppendRadioItem(icon_window.ID_CMD_CAMERA_NEAR,
				     "Camera Near")
		menu.AppendRadioItem(icon_window.ID_CMD_CAMERA_HIGH,
				     "Camera High")

		wx.EVT_MENU(win, icon_window.ID_CMD_ANIMATE,
			    self.evt_menu_animate)
		wx.EVT_MENU(win, icon_window.ID_CMD_LIGHT_NONE,
			    self.evt_menu_light)
		wx.EVT_MENU(win, icon_window.ID_CMD_LIGHT_ICON,
			    self.evt_menu_light)
		wx.EVT_MENU(win, icon_window.ID_CMD_LIGHT_ALT1,
			    self.evt_menu_light)
		wx.EVT_MENU(win, icon_window.ID_CMD_LIGHT_ALT2,
			    self.evt_menu_light)
		
		wx.EVT_MENU(win, icon_window.ID_CMD_CAMERA_FLAT,
			    self.evt_menu_camera)
		wx.EVT_MENU(win, icon_window.ID_CMD_CAMERA_DEFAULT,
			    self.evt_menu_camera)
		wx.EVT_MENU(win, icon_window.ID_CMD_CAMERA_NEAR,
			    self.evt_menu_camera)
		wx.EVT_MENU(win, icon_window.ID_CMD_CAMERA_HIGH,
			    self.evt_menu_camera)
		
	def __init__(self, parent, focus):
		self.failed = False
		wx.Window.__init__(self, parent)
		if mymcsup == None:
			self.failed = True
			return
		r = mymcsup.init_icon_renderer(focus.GetHandle(),
					       self.GetHandle())
		if r == -1:
			print "init_icon_renderer failed"
			self.failed = True
			return
		
		self.config = config = mymcsup.icon_config()
		config.animate = True

		self.menu = wx.Menu()
		self.append_menu_options(self, self.menu)
		self.set_lighting(self.ID_CMD_LIGHT_ALT2)
		self.set_camera(self.ID_CMD_CAMERA_DEFAULT)
		
		wx.EVT_CONTEXT_MENU(self, self.evt_context_menu)

	def __del__(self):
		if mymcsup != None:
			mymcsup.delete_icon_renderer()

	def update_menu(self, menu):
		"""Update the content menu according to the current config."""

		menu.Check(icon_window.ID_CMD_ANIMATE, self.config.animate)
		menu.Check(self.lighting_id, True)
		menu.Check(self.camera_id, True)
		
	def load_icon(self, icon_sys, icon):
		"""Pass the raw icon data to the support DLL for display."""

		if self.failed:
			return
		
		if icon_sys == None or icon == None:
			r = mymcsup.load_icon(None, 0, None, 0)
		else:
			r = mymcsup.load_icon(icon_sys, len(icon_sys),
					      icon, len(icon))
		if r != 0:
			print "load_icon", r
			self.failed = True

	def _set_lighting(self, lighting, vertex_diffuse, alt_lighting,
			 light_dirs, light_colours, ambient):
		if self.failed:
			return
		config = self.config
		config.lighting = lighting
		config.vertex_diffuse = vertex_diffuse
		config.alt_lighting = alt_lighting
		config.light_dirs = mkvec4arr3(light_dirs)
		config.light_colours = mkvec4arr3(light_colours)
		config.ambient = D3DXVECTOR4(*ambient)
		if mymcsup.set_config(config) == -1:
			self.failed = True

	def set_lighting(self, id):
		self.lighting_id = id
		self._set_lighting(**self.light_options[id])
		
	def set_animate(self, animate):
		if self.failed:
			return
		self.config.animate = animate
		if mymcsup.set_config(self.config) == -1:
			self.failed = True
		
	def _set_camera(self, camera):
		if self.failed:
			return
		self.config.camera = mymcsup.D3DXVECTOR3(*camera)
		if mymcsup.set_config(self.config) == -1:
			self.failed = True

	def set_camera(self, id):
		self.camera_id = id
		self._set_camera(self.camera_options[id])
		
	def evt_context_menu(self, event):
		self.update_menu(self.menu)
		self.PopupMenu(self.menu)

	def evt_menu_animate(self, event):
		self.set_animate(not self.config.animate)

	def evt_menu_light(self, event):
		self.set_lighting(event.GetId())

	def evt_menu_camera(self, event):
		self.set_camera(event.GetId())

class gui_config(wx.Config):
	"""A class for holding the persistant configuration state."""

	memcard_dir = "Memory Card Directory"
	savefile_dir = "Save File Directory"
	ascii = "ASCII Descriptions"
	
	def __init__(self):
		wx.Config.__init__(self, "mymc", "Ross Ridge",
				   style = wx.CONFIG_USE_LOCAL_FILE)

	def get_memcard_dir(self, default = None):
		return self.Read(gui_config.memcard_dir, default)

	def set_memcard_dir(self, value):
		return self.Write(gui_config.memcard_dir, value)

	def get_savefile_dir(self, default = None):
		return self.Read(gui_config.savefile_dir, default)

	def set_savefile_dir(self, value):
		return self.Write(gui_config.savefile_dir, value)

	def get_ascii(self, default = False):
		return bool(self.ReadInt(gui_config.ascii, int(bool(default))))

	def set_ascii(self, value):
		return self.WriteInt(gui_config.ascii, int(bool(value)))

def add_tool(toolbar, id, label, ico):
	tbsize = toolbar.GetToolBitmapSize()
	bmp = get_icon_resource_bmp(ico, tbsize)
	return toolbar.AddLabelTool(id, label, bmp, shortHelp = label)

class gui_frame(wx.Frame):
	"""The main top level window."""
	
	ID_CMD_EXIT = wx.ID_EXIT
	ID_CMD_OPEN = wx.ID_OPEN
	ID_CMD_EXPORT = 103
	ID_CMD_IMPORT = 104
	ID_CMD_DELETE = wx.ID_DELETE
	ID_CMD_ASCII = 106
	
	def message_box(self, message, caption = "mymc", style = wx.OK,
			x = -1, y = -1):
		return wx.MessageBox(message, caption, style, self, x, y)

	def error_box(self, msg):
		return self.message_box(msg, "Error", wx.OK | wx.ICON_ERROR)
		
	def mc_error(self, value, filename = None):
		"""Display a message box for EnvironmentError exeception."""

		if filename == None:
			filename = getattr(value, "filename")
		if filename == None:
			filename = self.mcname
		if filename == None:
			filename = "???"
					
		strerror = getattr(value, "strerror", None)
		if strerror == None:
			strerror = "unknown error"
			
		return self.error_box(filename + ": " + strerror)

	def __init__(self, parent, title, mcname = None):
		self.f = None
		self.mc = None
		self.mcname = None
		self.icon_win = None

		size = (750, 350)
		if mymcsup == None:
			size = (500, 350)
		wx.Frame.__init__(self, parent, wx.ID_ANY, title, size = size)

		wx.EVT_CLOSE(self, self.evt_close)

		self.config = gui_config()
		self.title = title

		self.SetIcons(get_icon_resource("mc4.ico"))
				
		wx.EVT_MENU(self, self.ID_CMD_EXIT, self.evt_cmd_exit)
		wx.EVT_MENU(self, self.ID_CMD_OPEN, self.evt_cmd_open)
		wx.EVT_MENU(self, self.ID_CMD_EXPORT, self.evt_cmd_export)
		wx.EVT_MENU(self, self.ID_CMD_IMPORT, self.evt_cmd_import)
		wx.EVT_MENU(self, self.ID_CMD_DELETE, self.evt_cmd_delete)
		wx.EVT_MENU(self, self.ID_CMD_ASCII, self.evt_cmd_ascii)
		
		filemenu = wx.Menu()
		filemenu.Append(self.ID_CMD_OPEN, "&Open...",
				"Opens an existing PS2 memory card image.")
		filemenu.AppendSeparator()
		self.export_menu_item = filemenu.Append(
			self.ID_CMD_EXPORT, "&Export...",
			"Export a save file from this image.")
		self.import_menu_item = filemenu.Append(
			self.ID_CMD_IMPORT, "&Import...",
			"Import a save file into this image.")
		self.delete_menu_item = filemenu.Append(
			self.ID_CMD_DELETE, "&Delete")
		filemenu.AppendSeparator()
		filemenu.Append(self.ID_CMD_EXIT, "E&xit")

		optionmenu = wx.Menu()
		self.ascii_menu_item = optionmenu.AppendCheckItem(
			self.ID_CMD_ASCII, "&ASCII Descriptions",
			"Show descriptions in ASCII instead of Shift-JIS")


		wx.EVT_MENU_OPEN(self, self.evt_menu_open);

		self.CreateToolBar(wx.TB_HORIZONTAL)
		self.toolbar = toolbar = self.GetToolBar()
		tbsize = (32, 32)
		toolbar.SetToolBitmapSize(tbsize)
		add_tool(toolbar, self.ID_CMD_OPEN, "Open", "mc2.ico")
		toolbar.AddSeparator()
		add_tool(toolbar, self.ID_CMD_IMPORT, "Import", "mc5b.ico")
		add_tool(toolbar, self.ID_CMD_EXPORT, "Export", "mc6a.ico")
		toolbar.Realize()

		self.statusbar = self.CreateStatusBar(2,
						      style = wx.ST_SIZEGRIP)
		self.statusbar.SetStatusWidths([-2, -1])
		
		panel = wx.Panel(self, wx.ID_ANY, (0, 0))

		self.dirlist = dirlist_control(panel,
					       self.evt_dirlist_item_focused,
					       self.evt_dirlist_select,
					       self.config)
		if mcname != None:
			self.open_mc(mcname)
		else:
			self.refresh()

		sizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(self.dirlist, 2, wx.EXPAND)
		sizer.AddSpacer(5)

		icon_win = None
		if mymcsup != None:
			icon_win = icon_window(panel, self)
			if icon_win.failed:
				icon_win.Destroy()
				icon_win = None
		self.icon_win = icon_win
		
		if icon_win == None:
			self.info1 = None
			self.info2 = None
		else:
			self.icon_menu = icon_menu = wx.Menu()
			icon_win.append_menu_options(self, icon_menu)
			optionmenu.AppendSubMenu(icon_menu, "Icon Window")
			title_style =  wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE
			
			self.info1 = wx.StaticText(panel, -1, "",
						   style = title_style)
			self.info2 = wx.StaticText(panel, -1, "",
						   style = title_style)
			# self.info3 = wx.StaticText(panel, -1, "")

			info_sizer = wx.BoxSizer(wx.VERTICAL)
			info_sizer.Add(self.info1, 0, wx.EXPAND)
			info_sizer.Add(self.info2, 0, wx.EXPAND)
			# info_sizer.Add(self.info3, 0, wx.EXPAND)
			info_sizer.AddSpacer(5)
			info_sizer.Add(icon_win, 1, wx.EXPAND)

			sizer.Add(info_sizer, 1, wx.EXPAND | wx.ALL,
				  border = 5)

		menubar = wx.MenuBar()
		menubar.Append(filemenu, "&File")
		menubar.Append(optionmenu, "&Options")
		self.SetMenuBar(menubar)

		
		panel.SetSizer(sizer)
		panel.SetAutoLayout(True)
		sizer.Fit(panel)

		self.Show(True)

		if self.mc == None:
			self.evt_cmd_open()

	def _close_mc(self):
		if self.mc != None:
			try:
				self.mc.close()
			except EnvironmentError, value:
				self.mc_error(value)
			self.mc = None
		if self.f != None:
			try:
				self.f.close()
			except EnvironmentError, value:
				self.mc_error(value)
			self.f = None
		self.mcname = None
		
	def refresh(self):
		try:
			self.dirlist.update(self.mc)
		except EnvironmentError, value:
			self.mc_error(value)
			self._close_mc()
			self.dirlist.update(None)

		mc = self.mc
		
		self.toolbar.EnableTool(self.ID_CMD_IMPORT, mc != None)
		self.toolbar.EnableTool(self.ID_CMD_EXPORT, False)

		if mc == None:
			status = "No memory card image"
		else:
			free = mc.get_free_space() / 1024
			limit = mc.get_allocatable_space() / 1024
			status = "%dK of %dK free" % (free, limit)
		self.statusbar.SetStatusText(status, 1)

	def open_mc(self, filename):
		self._close_mc()
		self.statusbar.SetStatusText("", 1)
		if self.icon_win != None:
			self.icon_win.load_icon(None, None)
		
		f = None
		try:
			f = file(filename, "r+b")
			mc = ps2mc.ps2mc(f)
		except EnvironmentError, value:
			if f != None:
				f.close()
			self.mc_error(value, filename)
			self.SetTitle(self.title)
			self.refresh()
			return

		self.f = f
		self.mc = mc
		self.mcname = filename
		self.SetTitle(filename + " - " + self.title)
		self.refresh()

	def evt_menu_open(self, event):
		self.import_menu_item.Enable(self.mc != None)
		selected = self.mc != None and len(self.dirlist.selected) > 0
		self.export_menu_item.Enable(selected)
		self.delete_menu_item.Enable(selected)
		self.ascii_menu_item.Check(self.config.get_ascii())
		if self.icon_win != None:
			self.icon_win.update_menu(self.icon_menu)

	def evt_dirlist_item_focused(self, event):
		if self.icon_win == None:
			return
		
		mc = self.mc

		i = event.GetData()
		(ent, icon_sys, size, title) = self.dirlist.dirtable[i]
		self.info1.SetLabel(title[0])
		self.info2.SetLabel(title[1])

		a = ps2save.unpack_icon_sys(icon_sys)
		try:
			mc.chdir("/" + ent[8])
			f = mc.open(a[15], "rb")
			try: 
				icon = f.read()
			finally:
				f.close()
		except EnvironmentError, value:
			print "icon failed to load", value
			self.icon_win.load_icon(None, None)
			return

		self.icon_win.load_icon(icon_sys, icon)

	def evt_dirlist_select(self, event):
		self.toolbar.EnableTool(self.ID_CMD_IMPORT, self.mc != None)
		self.toolbar.EnableTool(self.ID_CMD_EXPORT,
					len(self.dirlist.selected) > 0)

	def evt_cmd_open(self, event = None):
		fn = wx.FileSelector("Open Memory Card Image",
				     self.config.get_memcard_dir(""),
				     "Mcd001.ps2", "ps2", "*.ps2",
				     wx.FD_FILE_MUST_EXIST | wx.FD_OPEN,
				     self)
		if fn == "":
			return
		self.open_mc(fn)
		if self.mc != None:
			dirname = os.path.dirname(fn)
			if os.path.isabs(dirname):
				self.config.set_memcard_dir(dirname)

	def evt_cmd_export(self, event):
		mc = self.mc
		if mc == None:
			return
		
		selected = self.dirlist.selected
		dirtable = self.dirlist.dirtable
		sfiles = []
		for i in selected:
			dirname = dirtable[i][0][8]
			try:
				sf = mc.export_save_file("/" + dirname)
				longname = ps2save.make_longname(dirname, sf)
				sfiles.append((dirname, sf, longname))
			except EnvironmentError, value:
				self.mc_error(value. dirname)

		if len(sfiles) == 0:
			return
		
		dir = self.config.get_savefile_dir("")
		if len(selected) == 1:
			(dirname, sf, longname) = sfiles[0]
			fn = wx.FileSelector("Export " + dirname,
					     dir, longname, "psu",
					     "EMS save file (.psu)|*.psu"
					     "|MAXDrive save file (.max)"
					     "|*.max",
					     (wx.FD_OVERWRITE_PROMPT
					      | wx.FD_SAVE),
					     self)
			if fn == "":
				return
			try:
				f = file(fn, "wb")
				try:
					if fn.endswith(".max"):
						sf.save_max_drive(f)
					else:
						sf.save_ems(f)
				finally:
					f.close()
			except EnvironmentError, value:
				self.mc_error(value, fn)
				return

			dir = os.path.dirname(fn)
			if os.path.isabs(dir):
				self.config.set_savefile_dir(dir)

			self.message_box("Exported " + fn + " successfully.")
			return
		
		dir = wx.DirSelector("Export Save Files", dir, parent = self)
		if dir == "":
			return
		count = 0
		for (dirname, sf, longname) in sfiles:
			fn = os.path.join(dir, longname) + ".psu"
			try:
				f = file(fn, "wb")
				sf.save_ems(f)
				f.close()
				count += 1
			except EnvironmentError, value:
				self.mc_error(value, fn)
		if count > 0:
			if os.path.isabs(dir):
				self.config.set_savefile_dir(dir)
			self.message_box("Exported %d file(s) successfully."
					 % count)
			

	def _do_import(self, fn):
		sf = ps2save.ps2_save_file()
		f = file(fn, "rb")
		try:
			ft = ps2save.detect_file_type(f)
			f.seek(0)
			if ft == "max":
				sf.load_max_drive(f)
			elif ft == "psu":
				sf.load_ems(f)
			elif ft == "cbs":
				sf.load_codebreaker(f)
			elif ft == "sps":
				sf.load_sharkport(f)
			elif ft == "npo":
				self.error_box(fn + ": nPort saves"
					       " are not supported.")
				return
			else:
				self.error_box(fn + ": Save file format not"
					       " recognized.")
				return
		finally:
			f.close()

		if not self.mc.import_save_file(sf, True):
			self.error_box(fn + ": Save file already present.")
		
	def evt_cmd_import(self, event):
		if self.mc == None:
			return
		
		dir = self.config.get_savefile_dir("")
		fd = wx.FileDialog(self, "Import Save File", dir,
				   wildcard = ("PS2 save files"
					       " (.cbs;.psu;.max;.sps;.xps)"
					       "|*.cbs;*.psu;*.max;*.sps;*.xps"
					       "|All files|*.*"),
				   style = (wx.FD_OPEN | wx.FD_MULTIPLE
					    | wx.FD_FILE_MUST_EXIST))
		if fd == None:
			return
		r = fd.ShowModal()
		if r == wx.ID_CANCEL:
			return

		success = None
		for fn in fd.GetPaths():
			try:
				self._do_import(fn)
				success = fn
			except EnvironmentError, value:
				self.mc_error(value, fn)

		if success != None:
			dir = os.path.dirname(success)
			if os.path.isabs(dir):
				self.config.set_savefile_dir(dir)
		self.refresh()

	def evt_cmd_delete(self, event):
		mc = self.mc
		if mc == None:
			return
		
		selected = self.dirlist.selected
		dirtable = self.dirlist.dirtable

		dirnames = [dirtable[i][0][8]
			    for i in selected]
		if len(selected) == 1:
			title = dirtable[list(selected)[0]][3]
			s = dirnames[0] + " (" + single_title(title) + ")"
		else:
			s = ", ".join(dirnames)
			if len(s) > 200:
				s = s[:200] + "..."
		r = self.message_box("Are you sure you want to delete "
				     + s + "?",
				     "Delete Save File Confirmation",
				     wx.YES_NO)
		if r != wx.YES:
			return

		for dn in dirnames:
			try:
				mc.rmdir("/" + dn)
			except EnvironmentError, value:
				self.mc_error(value, dn)

		mc.check()
		self.refresh()

	def evt_cmd_ascii(self, event):
		self.config.set_ascii(not self.config.get_ascii())
		self.refresh()
		
	def evt_cmd_exit(self, event):
		self.Close(True)

	def evt_close(self, event):
		self._close_mc()
		self.Destroy()
		
def run(filename = None):
	"""Display a GUI for working with memory card images."""

	wx_app = wx.PySimpleApp()
	frame = gui_frame(None, "mymc", filename)
	return wx_app.MainLoop()
	
if __name__ == "__main__":
	import gc
	gc.set_debug(gc.DEBUG_LEAK)

	run("test.ps2")

 	gc.collect()
 	for o in gc.garbage:
 		print 
 		print o
 		if type(o) == ps2mc.ps2mc_file:
 			for m in dir(o):
 				print m, getattr(o, m)


# 	while True:
# 		for o in gc.garbage:
# 			if type(o) == ps2mc.ps2mc_file:
# 				for m in dir(o):
# 					if getattr(o, m) == None:
# 						continue
# 					if (m == "__del__"
# 					    or m == "__class__"
# 					    or m == "__dict__"
# 					    or m == "__weakref__"):
# 						continue
# 					print m
# 					setattr(o, m, None)
# 					o = None
# 					break
# 				break
# 		del gc.garbage[:]
# 		gc.collect()
