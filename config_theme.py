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
from autoedit import AutoEdit
from config import Configuration
from fields import File_Field, TextFile_Field
from folder import Folder


class Theme(Folder):

    class_id = 'config-theme'
    class_title = MSG(u'Theme')
    class_description = MSG(u'Allow to customize ikaaro skin')
    class_icon48 = 'icons/48x48/theme.png'

    # Fields
    logo = File_Field(title=MSG(u'Logo'))
    favicon = File_Field(title=MSG(u'Favicon'))
    banner = File_Field(title=MSG(u'Banner'))
    style = TextFile_Field(title=MSG(u'CSS Style'), class_handler=TextFile)


    def init_resource(self, **kw):
        super(Theme, self).init_resource(**kw)
        # Access
        self.set_value('share', 'everybody')
        # CSS file
        path = get_abspath('ui/themes/style.css')
        data = open(path).read()
        self.set_value('style', data)
        # Logo
        path = get_abspath('ui/themes/logo.png')
        data = open(path).read()
        self.set_value('logo', data)
        # Banner
        path = get_abspath('ui/themes/banner.jpg')
        data = open(path).read()
        self.set_value('banner', data)

    # Views
    class_views = ['edit', 'browse_content', 'preview_content', 'links',
                   'backlinks', 'commit_log']

    edit = AutoEdit(fields=['favicon', 'logo', 'banner', 'style', 'share'])

    # Configuration
    config_name = 'theme'
    config_group = 'webmaster'



# Register
Configuration.register_module(Theme)
