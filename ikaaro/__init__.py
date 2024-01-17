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

from sys import stderr

# Import from itools
from itools.core import get_abspath
from itools.gettext import register_domain

# Import from ikaaro
from .root import Root
from .file import File
from .folder import Folder
from .registry import register_document_type
from . import text
from .webpage import WebPage

# Import core config modules
from . import config_access
from . import config_captcha
from . import config_footer
from . import config_groups
from . import config_mail
from . import config_menu
from . import config_models
from . import config_register
from . import config_seo
from . import config_theme

# Import required modules
from . import users


# Check for required software
try:
    import itools.office.doctotext
    assert itools.office.doctotext # Silence pyflakes
except ImportError:
    print('DOC indexation: You need to install wv2 and reinstall itools.', file=stderr)

# The version
__version__ = "0.80.10"
__version_info__ = tuple(
    int(num) if num.isdigit() else num
    for num in __version__.replace("-", ".", 1).split(".")
)

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
