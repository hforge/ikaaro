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
from itools.database import PhraseQuery
from itools.datatypes import Enumerate
from itools.gettext import MSG

# Import from ikaaro
from autoedit import AutoEdit
from autoform import SelectWidget
from config import Configuration
from config_common import NewInstance_Local
from config_groups import UserGroupsDatatype
from config_searches import Config_Searches, SavedSearch
from fields import Select_Field
from registry import register_document_type
from table import Table
from table_views import Table_AddRecord, Table_EditRecord
from workflow import StaticStateEnumerate


class PermissionsDatatype(Enumerate):

    title = MSG(u'Permission')
    options = [
        {'name': 'view', 'value': MSG(u'View')},
        {'name': 'edit', 'value': MSG(u'Remove and modify')},
        {'name': 'add', 'value': MSG(u'Add')},
        {'name': 'wf_request', 'value': MSG(u'Request publication')},
        {'name': 'wf_publish', 'value': MSG(u'Publish and unpublish')}]


class SearchWorkflowState_Widget(SelectWidget):
    multiple = True
    has_empty_option = False


class SavedSearch_Content(SavedSearch):

    class_id = 'saved-search-content'
    class_title = MSG(u'Saved Search - Content')

    fields = SavedSearch.fields + ['search_workflow_state']
    search_workflow_state = Select_Field(multiple=True,
                                         datatype=StaticStateEnumerate,
                                         widget=SearchWorkflowState_Widget)

    # Views
    _fields = ['title', 'search_workflow_state']
    edit = AutoEdit(fields=_fields)
    new_instance = NewInstance_Local(fields=_fields)

    def get_search_query(self):
        query = super(SavedSearch_Content, self).get_search_query()
        query.append(PhraseQuery('is_content', True))
        return query


class SavedSearchesDatatype(Enumerate):

    def get_options(self):
        return [ {'name': x.name, 'value': x.get_title()}
                 for x in self.config.get_resources('searches') ]



class ConfigAccess_Handler(TableFile):

    record_properties = {
        'permission': PermissionsDatatype(mandatory=True),
        'group': UserGroupsDatatype(mandatory=True, title=MSG(u'User group')),
        'resources': SavedSearchesDatatype(title=MSG(u'Content')),
        }



class ConfigAccess(Table):

    class_id = 'config-access'
    class_version = '20110606'
    class_title = MSG(u'Access Control')
    class_description = MSG(u'Choose the security policy.')
    class_icon48 = 'icons/48x48/lock.png'

    table = Table.table(class_handler=ConfigAccess_Handler)

    # Configuration
    config_name = 'access'
    config_group = 'access'

    # API
    def has_permission(self, user, permission, resource=None):
        # 1. Ownership
        if user and resource and user.name == resource.get_owner():
            return True

        # 2. Configuration
        searches = self.get_resource('../searches')

        user_groups = set(['everybody'])
        if user:
            user_groups.add('authenticated')
            user_groups.update(user.get_property('groups'))

        table = self.handler
        for record in table.get_records():
            if table.get_record_value(record, 'permission') == permission:
                group_name = table.get_record_value(record, 'group')
                if group_name in user_groups:
                    if resource is None:
                        return True
                    search = table.get_record_value(record, 'resources')
                    if search is None:
                        return True
                    search = searches.get_resource(search, soft=True)
                    if search and search.match_resource(resource):
                        return True

        return False


    # User interface
    def get_schema(self):
        schema = super(ConfigAccess, self).get_schema()
        config = self.parent
        schema['group'] = schema['group'](config=config)
        schema['resources'] = schema['resources'](config=config)
        return schema

    _fields = ['permission', 'group', 'resources']
    add_record = Table_AddRecord(fields=_fields)
    edit_record = Table_EditRecord(fields=_fields)



# Register
Configuration.register_plugin(ConfigAccess)
register_document_type(SavedSearch_Content, Config_Searches.class_id)
