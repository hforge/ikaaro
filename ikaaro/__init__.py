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
from sys import stderr

# Import from itools
from itools.core import get_abspath, get_version
from itools.gettext import register_domain

# Import from ikaaro
from file import File
from folder import Folder
from registry import register_document_type
from root import Root
import text
from webpage import WebPage

# Import core config modules
import config_access
import config_captcha
import config_footer
import config_groups
import config_mail
import config_menu
import config_models
import config_register
import config_seo
import config_theme


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
__version__ = get_version()


# Import required modules
import users

# Register the itools domain
path = get_abspath('locale')
register_domain('ikaaro', path)

# Register document types
register_document_type(WebPage)
register_document_type(Folder)
register_document_type(File)

# Silent pyflakes
Root, text, users,
config_access, config_captcha, config_footer, config_groups,
config_mail, config_menu, config_models, config_register,
config_seo, config_theme,
