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
from itools.core import proto_property
from itools.database import PhraseQuery
from itools.gettext import MSG
from itools.web import get_context

# Import from ikaaro
from autoedit import AutoEdit
from buttons import RemoveButton
from config import Configuration
from config_common import NewResource_Local, NewInstance_Local
from config_groups import UserGroupsDatatype
from config_searches import Config_Searches, SavedSearch
from fields import Select_Field
from folder import Folder
from folder_views import Folder_BrowseContent
from registry import register_document_type
from resource_ import DBResource
from workflow import State_Field


###########################################################################
# Saved searches
###########################################################################
class SavedSearch_Content(SavedSearch):

    class_id = 'saved-search-content'
    class_title = MSG(u'Saved Search - Content')

    fields = SavedSearch.fields + ['search_state']
    search_state = State_Field(multiple=True)

    # Views
    _fields = ['title', 'search_state']
    edit = AutoEdit(fields=_fields)
    new_instance = NewInstance_Local(fields=_fields)

    def get_search_query(self):
        query = super(SavedSearch_Content, self).get_search_query()
        query.append(PhraseQuery('is_content', True))
        return query



class SavedSearches_Field(Select_Field):

    @proto_property
    def options(self):
        config = get_context().root.get_resource('config')
        return [ {'name': x.name, 'value': x.get_title()}
                 for x in config.get_resources('searches') ]



class ConfigAccess_Rule_NewInstance(NewInstance_Local):

    fields = ['permission', 'group', 'resources']

    def get_new_resource_name(self, form):
        container = form['container']
        return container.get_new_id()


###########################################################################
# Access rule
###########################################################################
class Permissions_Field(Select_Field):

    title = MSG(u'Permission')
    options = [
        {'name': 'view', 'value': MSG(u'View')},
        {'name': 'edit', 'value': MSG(u'Remove and modify')},
        {'name': 'add', 'value': MSG(u'Add')},
        {'name': 'change_state', 'value': MSG(u'Change workflow state')}]



class ConfigAccess_Rule(DBResource):

    class_id = 'config-access-rule'
    class_title = MSG(u'Access rule')

    # Fields
    fields = DBResource.fields + ['permission', 'group', 'resources']
    permission = Permissions_Field(required=True)
    group = Select_Field(required=True, title=MSG(u'User group'),
                         datatype=UserGroupsDatatype)
    resources = SavedSearches_Field(title=MSG(u'Content'))

    # Views
    class_views = ['edit', 'commit_log']
    new_instance = ConfigAccess_Rule_NewInstance()
    edit = AutoEdit(fields=['permission', 'group', 'resources'])



###########################################################################
# Configuration module
###########################################################################
class ConfigAccess_Browse(Folder_BrowseContent):

    query_schema = Folder_BrowseContent.query_schema.copy()
    query_schema['sort_by'] = query_schema['sort_by'](default='group')

    search_widgets = None

    table_columns = [
        ('checkbox', None),
        ('abspath', MSG(u'Path')),
        #('title', MSG(u'Title')),
        ('group', MSG(u'Group')),
        ('resources', MSG(u'Resources')),
        ('permission', MSG(u'Permission'))]
        #('mtime', MSG(u'Last Modified')),
        #('last_author', MSG(u'Last Author'))]

    table_actions = [RemoveButton]

    def get_item_value(self, resource, context, item, column):
        if column == 'resources':
            brain, item_resource = item
            value = item_resource.get_value(column)
            if value is None:
                return None
            search = resource.get_resource('/config/searches/%s' % value)
            return (search.get_title(), str(search.abspath))

        proxy = super(ConfigAccess_Browse, self)
        return proxy.get_item_value(resource, context, item, column)



class ConfigAccess(Folder):

    class_id = 'config-access'
    class_version = '20110606'
    class_title = MSG(u'Access Control')
    class_description = MSG(u'Choose the security policy.')
    class_icon48 = 'icons/48x48/lock.png'

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
            user_groups.update(user.get_value('groups'))

        for rule in self.get_resources():
            if rule.get_value('permission') == permission:
                group_name = rule.get_value('group')
                if group_name in user_groups:
                    if resource is None:
                        return True
                    search = rule.get_value('resources')
                    if search is None:
                        return True
                    search = searches.get_resource(search, soft=True)
                    if search and search.match_resource(resource):
                        return True

        return False


    def get_new_id(self):
        ids = [ int(x) for x in self.get_names() ]
        return str(max(ids) + 1) if ids else '0'


    def get_document_types(self):
        return [ConfigAccess_Rule]


    # Views
    class_views = ['browse_content', 'add_rule', 'edit', 'commit_log']
    browse_content = ConfigAccess_Browse()
    add_rule = NewResource_Local(title=MSG(u'Add rule'))



# Register
Configuration.register_plugin(ConfigAccess)
register_document_type(SavedSearch_Content, Config_Searches.class_id)
