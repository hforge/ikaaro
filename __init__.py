# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2006-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2008 Sylvain Taverne <sylvain@itaapy.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Import from the Standard Library
from os import getenv, listdir

# Import from itools
from itools import get_abspath
from itools.gettext import register_domain
from itools.utils import get_version

# Import from ikaaro
from calendar_ import CalendarTable
from file import File
from folder import Folder
from html import WebPage
import root


# The version
__version__ = get_version()


# Register the itools domain
path = get_abspath('locale')
register_domain('ikaaro', path)

# Register document types
Folder.register_document_type(WebPage)
Folder.register_document_type(Folder)
Folder.register_document_type(File)
Folder.register_document_type(CalendarTable)

# Import ikaaro sub-packages (NOTE must be imported after so they are
# register after)
import forum
import tracker
try:
    import docutils
except ImportError:
    print "docutils is not installed, wiki deactivated."
else:
    import wiki


###########################################################################
# Check for required software
###########################################################################
cmds = ['wvText', 'xlhtml', 'ppthtml', 'pdftotext', 'unrtf']

paths = getenv('PATH').split(':')
all_names = set()
for path in paths:
    path = path.strip()
    try:
        names = listdir(path)
    except OSError:
        pass
    else:
        all_names = all_names.union(names)

for name in cmds:
    if name not in all_names:
        print 'You need to install the command "%s".' % name
