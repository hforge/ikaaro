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
from itools.csv import Table as TableFile
from itools.datatypes import Enumerate, String
from itools.gettext import MSG

# Import from ikaaro
from autoform import SelectWidget
from config import Configuration
from config_groups import UserGroupsDatatype
from table import Table


class PermissionsDatatype(Enumerate):

    options = [
        {'name': 'view_public', 'value': MSG(u'View public content')},
        {'name': 'view_private', 'value': MSG(u'View non public content')},
        {'name': 'edit_public',
         'value': MSG(u'Add, remove and modify public content')},
        {'name': 'edit_private',
         'value': MSG(u'Add, remove and modify non public content')},
        {'name': 'wf_request',
         'value': MSG(u'Request publication of content')},
        {'name': 'wf_publish',
         'value': MSG(u'Publish and unpublish content')},
        {'name': 'config', 'value': MSG(u'Manage configuration')},
    ]



class ConfigAccess_Handler(TableFile):

    record_properties = {
        'permission': PermissionsDatatype(mandatory=True),
        'group': String(mandatory=True)}



class ConfigAccess(Table):

    class_id = 'config-access'
    class_version = '20110606'
    class_title = MSG(u'Access Control')
    class_description = MSG(u'Choose the security policy.')
    class_icon48 = 'icons/48x48/lock.png'
    class_handler = ConfigAccess_Handler

    # Configuration
    config_name = 'access'
    config_group = 'access'

    # API
    def has_permission(self, user, permission):
        table = self.handler
        for record in table.get_records():
            if table.get_record_value(record, 'permission') == permission:
                group_name = table.get_record_value(record, 'group')
                if group_name == 'everybody':
                    # Anonymous
                    return True
                elif group_name == 'authenticated':
                    # Authenticated
                    if user:
                        return True
                elif user:
                    # Normal groups
                    group = self.parent.get_resource('groups/%s' % group_name)
                    if user.name in group.get_property('members'):
                        return True

        return False


    # User interface
    def get_schema(self):
        schema = super(ConfigAccess, self).get_schema()
        config_groups = self.parent.get_resource('groups')
        schema['group'] = UserGroupsDatatype(mandatory=True,
                                             config_groups=config_groups)
        return schema

    form = [
        SelectWidget('permission', title=MSG(u'Permission')),
        SelectWidget('group', title=MSG(u'User group'))]



Configuration.register_plugin(ConfigAccess)
