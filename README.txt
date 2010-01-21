
ikaaro is a Content Management System built on Python & itools, among
other feautres it provides:

 - Content & Document Management.
 - Collaboration with the Wiki module, the issue tracker, etc.
 - Multiple web sites in one instance, with separate access rights.
 - Mulitilingual interfaces and content.

The scripts included are:

  icms-forget.py
  icms-init.py
  icms-start.py
  icms-stop.py
  icms-update.py
  icms-update-catalog.py


Requirements
=============

Software    Version  Used by           Home
----------  -------  ----------------  --------------------------------------
Python          2.6  ikaaro            http://www.python.org/
itools       0.60.0  ikaaro            http://www.hforge.org/itools
docutils        0.5  Wiki              http://docutils.sourceforge.net/
lpOD            0.8  Wiki ODT export   http://www.lpod-project.org/
guppy         0.1.8  Memory profiling  http://guppy-pe.sourceforge.net/

Check the itools requirements.


Install
=============

If you are reading this instructions you probably have already unpacked
the ikaaro tarball with the command line:

  $ tar xzf ikaaro-X.Y.Z.tar.gz

And changed the working directory this way:

  $ cd ikaaro-X.Y.Z

So now to install ikaaro you just need to type this:

  $ python setup.py install


Documentation
=============

The documentation is distributed as a separate package, ikaaro-docs.
The PDF file can be downloaded from http://www.hforge.org/ikaaro


Resources
=============

Home
http://www.hforge.org/ikaaro

Mailing list
http://www.hforge.org/community/
http://archives.hforge.org/index.cgi?list=itools

Bug Tracker
http://bugs.hforge.org


Copyright
=============

Copyright (C) 2003-2009 Juan David Ibáñez Palomar <jdavid@itaapy.com>
Copyright (C) 2005-2009 Luis Arturo Belmar-Letelier <luis@itaapy.com>
Copyright (C) 2005-2009 Hervé Cauwelier <herve@itaapy.com>
Copyright (C) 2005-2009 Nicolas Deram <nicolas@itaapy.com>

And others. Check the CREDITS file for complete list.

Includes some external free software:

Software        License  Home
--------------  -------  -----------------------------------------
jquery          GPL      http://jquery.com
TinyMCE         LGPL     http://tinymce.moxiecode.com
DHTML Calendar  LGPL     http://code.google.com/p/dyndatetime/

Most icons used are copyrighted by the Tango Desktop Project, and licensed
under the Creative Commons Attribution Share-Alike license, including the
modifications to them. (http://creativecommons.org/licenses/by-sa/2.5/)


License
=============

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

