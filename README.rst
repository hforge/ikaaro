
ikaaro is a Content Management System built on Python & itools, among
other feautres it provides:

 - Content & Document Management.
 - Collaboration with the calendar, issue tracker, etc.
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

Software    Version  Used by            Home
----------  -------  -----------------  -------------------------------------
Python          2.6  ikaaro             http://www.python.org/
itools       0.75.0  ikaaro             http://www.hforge.org/itools
utidylib             ikaaro (optional)  http://utidylib.berlios.de/
guppy         0.1.8  Memory profiling   http://guppy-pe.sourceforge.net/

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

Copyright (C) 2002-2011 The Ikaaro authors

Check the CREDITS.txt file for the list of authors.

Includes some external free software:

Software        License  Home
--------------  -------  -----------------------------------------
jQuery          GPL      http://jquery.com
TinyMCE         LGPL     http://tinymce.moxiecode.com
DHTML Calendar  LGPL     http://code.google.com/p/dyndatetime/
Edit area       LGPL     http://www.cdolivet.com/editarea/
Password meter  BSD      http://mypocket-technologies.com/jquery/

And media content:

- Most icons come from the Tango Desktop Project:
  http://tango.freedesktop.org/Tango_Desktop_Project

- The banner comes from the "Personas for Firefox" project:
  http://www.getpersonas.com/en-US/persona/94524

  And is available under the "by-nc-sa" license:
  http://creativecommons.org/licenses/by-nc-sa/3.0/


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
