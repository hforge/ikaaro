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

# Import from standard library
from logging import getLogger, NullHandler
from sys import stderr

# Import from itools
from itools.core import get_abspath
from itools.gettext import register_domain

# Import from ikaaro
# Add class to register
from .root import Root
from .file import File
from .folder import Folder
from .registry import register_document_type
from . import text
from .webpage import WebPage


getLogger("ikaaro").addHandler(NullHandler())
getLogger("ikaaro.web").addHandler(NullHandler())
getLogger("ikaaro.update").addHandler(NullHandler())
getLogger("ikaaro.access").addHandler(NullHandler())
getLogger("ikaaro.cron").addHandler(NullHandler())


# Check for required software
for name, import_path, reason in [
        ("poppler", "itools.pdf.pdftotext", "PDF indexation"),
        ("wv2", "itools.office.doctotext", "DOC indexation"),
        ("xlrd", "xlrd", "XLS indexation")]:
    try:
        __import__(import_path)
    except ImportError:
        stderr.write('%s: You need to install "%s" and reinstall itools.\n' % (
            reason, name))


# The version
__version__ = "0.80.7"
__version_info__ = tuple(
    int(num) if num.isdigit() else num
    for num in __version__.replace("-", ".", 1).split(".")
)

# Import required modules
from . import users

# Register the itools domain
path = get_abspath('locale')
register_domain('ikaaro', path)

# Register document types
register_document_type(WebPage)
register_document_type(Folder)
register_document_type(File)