# -*- coding: UTF-8 -*-
# Copyright (C) 2010 Henry Obein <henry@itaapy.com>
# Copyright (C) 2011 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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

# Import from itools
from itools.core import get_abspath
from itools.gettext import MSG
from itools.handlers import TextFile

# Import from ikaaro
from .autoedit import AutoEdit
from .config import Configuration
from .fields import File_Field, TextFile_Field
from .folder import Folder


class Theme(Folder):

    class_id = 'config-theme'
    class_title = MSG('Theme')
    class_description = MSG('Allow to customize ikaaro skin')
    class_icon_css = 'fa-star'

    # Fields
    logo = File_Field(title=MSG('Logo'))
    favicon = File_Field(title=MSG('Favicon'))
    banner = File_Field(title=MSG('Banner'))
    style = TextFile_Field(title=MSG('CSS Style'), class_handler=TextFile)


    def init_resource(self, **kw):
        super(Theme, self).init_resource(**kw)
        # Access
        self.set_value('share', 'everybody')
        # CSS file
        path = get_abspath('ui/ikaaro/themes/style.css')
        data = open(path).read()
        self.set_value('style', data)
        # Logo
        path = get_abspath('ui/ikaaro/themes/logo.png')
        data = open(path, "rb").read()
        self.set_value('logo', data)
        # Banner
        path = get_abspath('ui/ikaaro/themes/banner.jpg')
        data = open(path, "rb").read()
        self.set_value('banner', data)

    # Views
    class_views = ['edit', 'browse_content', 'preview_content', 'links',
                   'backlinks']

    edit = AutoEdit(fields=['favicon', 'logo', 'banner', 'style', 'share'])

    # Configuration
    config_name = 'theme'
    config_group = 'webmaster'



# Register
Configuration.register_module(Theme)
