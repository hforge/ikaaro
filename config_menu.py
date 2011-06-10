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
from itools.csv import Property
from itools.gettext import MSG

# Import from ikaaro
from config import Configuration
from menu import MenuFolder


class ConfigMenu(MenuFolder):

    class_id = 'config-menu'
    class_description = MSG(u'Edit the global menu.')
    class_icon48 = 'icons/48x48/menu.png'

    def init_resource(self, **kw):
        super(ConfigMenu, self).init_resource(**kw)
        # Menu
        menu = self.get_resource('menu')
        menu.add_new_record({'path': '../../..',
                             'title': Property(u'Home', language='en'),
                             'target': '_top'})
        menu.add_new_record({'path': '../../../;contact',
                             'title': Property(u'Contact', language='en'),
                             'target': '_top'})

    # Configuration
    config_name = 'menu'
    config_group = 'webmaster'


Configuration.register_plugin(ConfigMenu)
