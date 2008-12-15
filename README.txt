
ikaaro is a Content Management System built on Python & itools, among
other feautres it provides:

 - content and document mangement (full index&search, metadata, etc.)
 - multilingual user interfaces and content
 - high level modules: wiki, forum, tracker, etc.

The scripts included are:

  icms-init.py
  icms-restore.py
  icms-start.py
  icms-start-server.py
  icms-start-spool.py
  icms-stop.py
  icms-update.py
  icms-update-catalog.py


Requirements
------------

Python 2.5.2 or later and itools 0.50 are required.

It is recommended to install PIL [1].  For the Wiki to work, docutils [2]
is required.

Apart from the Python packages listed above, the commands xlhtml, ppthtml,
pdftotext, wvText and unrtf are required to index some types of documents.

[1] http://www.pythonware.com/products/pil/
[2] http://docutils.sourceforge.net/


Install
-------

If you are reading this instructions you probably have already unpacked
the ikaaro tarball with the command line:

  $ tar xzf ikaaro-X.Y.Z.tar.gz

And changed the working directory this way:

  $ cd ikaaro-X.Y.Z

So now to install ikaaro you just need to type this:

  $ python setup.py install


Documentation
-------------

The documentation is distributed as a separate package, ikaaro-docs.
The PDF file can be downloaded from http://www.hforge.org/ikaaro


Resources
---------

Home
http://www.hforge.org/ikaaro

Mailing list
http://www.hforge.org/community/
http://archives.hforge.org/index.cgi?list=itools

Bug Tracker
http://bugs.hforge.org


Copyright
---------

Copyright (C) 2003-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
Copyright (C) 2005-2008 Luis Arturo Belmar-Letelier <luis@itaapy.com>
Copyright (C) 2005-2008 Hervé Cauwelier <herve@itaapy.com>
Copyright (C) 2005-2008 Nicolas Deram <nicolas@itaapy.com>

And others. Check the CREDITS file for complete list.

Includes the TinyMCE editor (http://tinymce.moxiecode.com/), available
under the terms and conditions of the GNU Lesser General Public License.

Includes the DHTML Calendar (http://www.dynarch.com/projects/calendar/),
authored by Mihai Bazon and published under the terms of the GNU Lesser
General Public License.

Most icons used are copyrighted by the Tango Desktop Project, and licensed
under the Creative Commons Attribution Share-Alike license, including the
modifications to them. (http://creativecommons.org/licenses/by-sa/2.5/)


License
-------

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

