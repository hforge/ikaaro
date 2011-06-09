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
from itools.gettext import MSG

# Import from ikaaro
from access import RoleAware_BrowseUsers, RoleAware_AddUser
from access import RoleAware_EditMembership
from config import Configuration
from resource_ import DBResource


class ConfigUsers(DBResource):

    class_id = 'config-users'
    class_version = '20110606'
    class_title = MSG(u'Users')
    class_description = MSG(u'Manage users.')
    class_icon48 = 'icons/48x48/userfolder.png'
    class_views = ['browse_users', 'add_user']

    browse_users = RoleAware_BrowseUsers()
    add_user = RoleAware_AddUser()
    edit_membership = RoleAware_EditMembership()


Configuration.register_plugin('users', ConfigUsers)
