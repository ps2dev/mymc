README.txt

By Ross Ridge
Pubic Domain

@(#) mymc README.txt 1.6 12/10/04 19:18:08


This file describes mymc, a utility for manipulating PlayStation 2
memory card images as used by the emulator PCSX2.  Its main purpose is
to allow save games to be imported and exported to and from these
images.  Both MAX Drive and EMS (.psu) save files are fully supported,
however save files in the SharkPort/X-Port and Code Breaker formats
can only be imported and not exported.  In addition to these basic
functions, mymc can also perform a number of other operations, like
creating new memory card images, viewing their contents, and adding
and extracting individual files.

A simple, hopefully easy to use, graphicial user interface (GUI) is
provided, but it's limitted to only basic operations.  More advanced
opterations require the use of a command line tool.  To install mymc,
unpack the downloaded ZIP archive to a new directory on your machine.
You can then run the GUI version of mymc by openning that newn
directory with Windows Explorer and double clicking on the "mymc-gui"
icon.  To make it easier to access, you can drag the "mymc-gui" icon
to either your Desktop, Start Menu or Quick Launch toolbar.  Make sure
if you do so, that you create a shortcut to "mymc-gui.exe".  If you
copy the file instead, the program won't work.

The command line utility can be invoked from the Windows Command
Prompt by using the "mymc" command.  The executable "mymc.exe" and
number of support files and these file must kept together in the same
directory.  To run the command you need to either add the directory
where you unpacked the distribution to your PATH or type the full
pathname of the executable.  For example if you unpacked mymc to a
directory named "c:\mymc" you need to enter "c:\mymc\mymc.exe" to run
the program.

The second important thing to note is that mymc is only "alpha"
quality software.  This means that has is been released without
extensive testing and may be unreliable.  While it works fine for me,
the author, it might not work as well for you.  For that reason you
should be careful how you use it, and prepared for the eventuality of
it corrupting your save game images or producing garbage save files.
If you're worried about this, one make things safer is to use two
memory card images.  Use the first image to load and save your games
with under PCSX2, and the second image to import and export saves
games using mysc.  Then use the PS2 browser to copy files between two
card images.


GUI TUTORIAL
============

The GUI for mymc is should be easy to use.  After starting mymc, you
can select the PS2 memory card image you want to work with by
selecting the "Open" command by pressing the first button on the
toolbar.  You can then import a save file clicking on the Import
toolbar button.  To export a save files, first select it and then
press the Export button.  You can delete a save file permanently from
your memory card, by selecting the "Delete" command from the File
menu.

Do not try to use mymc to modify a memory card image while PCSX2 is
running.  Doing so will corrupt your memory card.


COMMAND LINE TUTORIAL
=====================

The basic usage template for mysc is "mymc memcard.ps2 command".  The
first argument, "memcard.ps2" is the filename of the memory card image
while "command" is the name of the command you wish to use on the
image.  So for example, assuming you've installed mymc in "c:\mymc"
and you've installed PCSX2 in "c:\pcsx2" you could enter the following
command to see the contents of the memory card in the emulator's slot
1:

    c:\mymc\mymc c:\pcsx2\memcards\Mcd001.ps2 dir

You would see output something like this:

    BASLUS-20678USAGAS00             UNLIMITED SAGA
     154KB Not Protected             SYSTEMDATA

    BADATA-SYSTEM                    Your System
       5KB Not Protected             Configuration

    BASLUS-20488-0000D               SOTET<13>060:08
     173KB Not Protected             Arias

    7,800 KB Free

This is the simple "user friendly" way to view the contents of a
memory card.  It displays the same information you can see using the
PlayStation 2 memory card browser.  On the right is name of each save,
and on the left is the size and protection status of the save.  Also
on the left is one bit of information you won't see in the browser,
the directory name of the save file.  PlayStation 2 saves are actually
a collection of different files all stored in a single directory on
the memory card.  This is important information, because you need to
know it to export save files.

As mentioned above, if you know the directory name of a save, you can
export it.  Exporting a save creates a save file in either the EMS
(.psu) or MAX Drive (.max) format.  You can then transfer the save to
real PS2 memory using the appropriate tools.  You can also send the
saves to someone else to use or just keep them on your hard drive as a
backup.  The following command demonstrates how to export a save in
the EMS format using mymc:

    c:\mymc\mymc c:\pcsx2\memcards\Mcd001.ps2 export BASLUS-20448-0000D

This will create a file called "BASLUS-20448-0000D.psu" in the current
directory.  To create a file in the MAX format instead, use the export
command's -m option:

    c:\mymc\mymc c:\pcsx2\memcards\Mcd001.ps2 export -m BASLUS-20448-0000D

This creates a file named "BASLUS-20448-0000D.max".  Note the "-m"
option that appears after the "export" command.

Importing save files is similar.  The save file type is auto-detected,
so you don't need use an "-m" option with MAX Drive saves.  Here's a
couple of examples using each format:

    c:\mymc\mymc c:\pcsx2\memcards\Mcd001.ps2 import BASLUS-20035.psu
    c:\mymc\mymc c:\pcsx2\memcards\Mcd001.ps2 import 20062_3583_GTA3.max


ADVANCED NOTES
==============

    - To get general help with the command line utility use the "-h"
      global option (eg. "mymc -h").  To get help with a specific
      command use the "-h" option with that command (eg. "mymc x
      import -h").  In this later case, you need to specify a memory
      card image file, but it's ignored and so doesn't need to exist.

    - Both executables in the Windows version, "mymc.exe" and
      "mymc-gui.exe" do the same thing and support the same options.
      The difference is that "mymc" is console application, while
      "mymc-gui" is a Windows appliction.  Currently, using "mymc"
      to start the GUI will result in a fair amount debug messages
      being printed that are normally not seen "mymc-gui" is used.

    - It's possible to use mymc create images that are bigger (or
      smaller) than standard PS2 memory cards.  Be very careful if you
      do this, not all games may be compatible with such images.

    - The bad block list on images is ignored.  Since memory card
      images created with either PCSX2 or mymc won't have any bad
      blocks, this shouldn't be a problem unless you've somehow
      extracted a complete image from a real memory card and expect to
      copy it back.

    - The PS2 only uses at most 8,000 KB of a memory card, but there
      is actually 8,135 KB of allocatable space on a standard
      error-free memory card.  The extra 135 KB is reserved so that
      memory card with bad blocks don't appear to have less space than
      memory cards with fewer or no bad blocks.  Since there are no
      bad blocks on memory card images, mymc uses the full capacity
      provided by standard memory cards.


PYTHON SOURCE DISTRIBUTION
==========================

The "source code" distribution of mymc is provided for users of Linux
and other non-Windows operating systems.  It uses the same Python code
that the Windows distribution is built with (using py2exe) and
supports all the same functionality.  One big difference is that the
Windows DLL "mymcsup.dll" is not included and as a result compressing
and decompressing MAX Drive saves will be as much as 100 times slower.
The GUI mode is hasn't been extensively tested on non-Windows systems,
and the 3D display of save file icons requires the DLL.  The Python
source version should support big-endian machines, but this hasn't
been tested.
