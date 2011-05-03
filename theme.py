# -*- coding: UTF-8 -*-
# Copyright (C) 2010 Henry Obein <henry@itaapy.com>
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
from itools.core import merge_dicts, get_abspath
from itools.datatypes import URI
from itools.gettext import MSG
from itools.handlers import ro_database, File as FileHandler

# Import from ikaaro
from control_panel import ControlPanel
from file import Image
from folder import Folder
from folder_views import GoToSpecificDocument
from menu import MenuFolder
from registry import register_resource_class
from text import CSS
from theme_views import Theme_Edit, Theme_AddFavIcon, Theme_AddLogo



class Theme(Folder):

    class_id = 'theme'
    class_title = MSG(u'Theme')
    class_description = MSG(u'Allow to customize ikaaro skin')
    class_icon16 = 'icons/16x16/theme.png'
    class_icon48 = 'icons/48x48/theme.png'
    class_views = ['edit', 'edit_css', 'edit_menu', 'browse_content',
                   'preview_content', 'links', 'backlinks', 'commit_log',
                   'control_panel']
    __fixed_handlers__ = ['style', 'menu']

    add_favicon = Theme_AddFavIcon()
    add_logo = Theme_AddLogo()
    control_panel = GoToSpecificDocument(specific_document='../;control_panel',
                                         title=ControlPanel.title)
    edit = Theme_Edit()
    edit_css = GoToSpecificDocument(specific_document='style',
            access='is_allowed_to_edit', specific_view='edit',
            title=MSG(u'Edit CSS'))
    edit_menu = GoToSpecificDocument(specific_document='menu',
            access='is_allowed_to_edit', title=MSG(u'Edit menu'))

    class_schema = merge_dicts(
        Folder.class_schema,
        # Metadata
        favicon=URI(source='metadata', default=''),
        logo=URI(source='metadata', default=''))

    is_content = False


    def init_resource(self, **kw):
        Folder.init_resource(self, **kw)
        # Menu
        self.make_resource('menu', MenuFolder)
        # CSS file
        path = get_abspath('ui/themes/style.css')
        body = open(path).read()
        self.make_resource('style', CSS, extension='css', body=body,
                           state='public')
        # Logo
        path = get_abspath('ui/themes/logo.png')
        image = ro_database.get_handler(path, FileHandler)
        self.make_resource('logo', Image, body=image.to_str(),
                           extension='png', filename='logo.png',
                           format='image/png', state='public')
        self.set_property('logo', 'logo')
        # Banner
        path = get_abspath('ui/themes/banner.jpg')
        image = ro_database.get_handler(path, FileHandler)
        self.make_resource('banner', Image, body=image.to_str(),
                           extension='jpg', filename='banner.jpg',
                           format='image/jpeg', state='public')



###########################################################################
# Register
###########################################################################
register_resource_class(Theme)
