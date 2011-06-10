# -*- coding: UTF-8 -*-
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
from itools.core import merge_dicts
from itools.datatypes import Boolean
from itools.gettext import MSG

# Import from ikaaro
from autoedit import AutoEdit
from config import Configuration
from resource_ import DBResource



class ConfigRegister(DBResource):

    class_id = 'config-register'
    class_version = '20110606'
    class_title = MSG(u'User registration')
    class_description = MSG(u'Configuration the user registration process.')
    class_icon48 = 'icons/48x48/signin.png'

    class_schema = merge_dicts(
        DBResource.class_schema,
        is_open=Boolean(source='metadata', default=False,
                        title=MSG(u'Users can register by themselves')))

    # Views
    class_views = ['edit']
    edit = AutoEdit(title=class_description, fields=['is_open'])

    # Configuration
    config_name = 'register'
    config_group = 'access'


Configuration.register_plugin(ConfigRegister)
