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
from itools.database import AndQuery, OrQuery, PhraseQuery
from itools.datatypes import Enumerate
from itools.gettext import MSG
from itools.web import get_context

# Import from ikaaro
from autoedit import AutoEdit
from buttons import RemoveButton
from config import Configuration
from config_common import NewResource_Local, NewInstance_Local
from config_groups import UserGroupsDatatype
from fields import Select_Field
from folder import Folder
from folder_views import Folder_BrowseContent
from resource_ import DBResource
from utils import get_content_containers
from workflow import State_Field


###########################################################################
# Saved searches
###########################################################################
class Path_Datatype(Enumerate):

    def get_options(self):
        context = get_context()

        items = []
        for resource in get_content_containers(context, set()):
            path = resource.abspath
            title = '/' if not path else ('%s/' % path)
            items.append({'name': path, 'value': title, 'selected': False})

        return items


class Path_Field(Select_Field):

    datatype = Path_Datatype
    has_empty_option = False
    title = MSG(u'Path')



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



class AccessRule_Results(Folder_BrowseContent):

    title = MSG(u'View results')
    search_schema = {}
    search_widgets = []

    def get_items_query(self, resource, context):
        return [resource.get_search_query()]


class AccessRule(DBResource):

    class_id = 'config-access-rule'
    class_title = MSG(u'Access rule')

    # Fields
    fields = DBResource.fields + ['group', 'permission',
                                  'search_state', 'search_parent_paths']
    group = Select_Field(required=True, title=MSG(u'User group'),
                         datatype=UserGroupsDatatype)
    permission = Permissions_Field(required=True)
    search_state = State_Field(has_empty_option=True, default='')
    search_parent_paths = Path_Field()

    # Views
    class_views = ['edit', 'results', 'commit_log']
    _fields = ['group', 'permission', 'search_state', 'search_parent_paths']
    new_instance = NewInstance_Local(fields=_fields,
                                     automatic_resource_name=True)
    edit = AutoEdit(fields=_fields)
    results = AccessRule_Results()

    # API
    def get_search_query(self):
        # Search values
        query = AndQuery()
        for name in self.fields:
            if not name.startswith('search_'):
                continue
            value = self.get_value(name)
            if not value:
                continue
            field = self.get_field(name)
            name = name[7:]
            if field.multiple:
                subquery = [ PhraseQuery(name, x) for x in value ]
                if len(subquery) == 1:
                    subquery = subquery[0]
                else:
                    subquery = OrQuery(*subquery)
            else:
                subquery = PhraseQuery(name, value)
            query.append(subquery)

        query.append(PhraseQuery('is_content', True))
        return query


    def match_resource(self, resource):
        query = self.get_search_query()
        query.append(PhraseQuery('abspath', str(resource.abspath)))
        results = get_context().root.search(query)
        return len(results)



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
        ('permission', MSG(u'Permission')),
        ('search_state', MSG(u'State')),
        ('search_parent_paths', MSG(u'Path'))]
        #('mtime', MSG(u'Last Modified')),
        #('last_author', MSG(u'Last Author'))]

    table_actions = [RemoveButton]

#   def get_item_value(self, resource, context, item, column):
#       if column == 'search_state':
#           brain, item_resource = item
#           value = item_resource.get_value(column)
#           if value is None:
#               return None
#           search = resource.get_resource('/config/searches/%s' % value)
#           return (search.get_title(), str(search.abspath))

#       proxy = super(ConfigAccess_Browse, self)
#       return proxy.get_item_value(resource, context, item, column)



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
        owner = resource.get_owner() if resource else None
        if user and user.abspath == owner:
            return True

        # 2. User groups
        user_groups = set(['everybody'])
        if user:
            user_groups.add('authenticated')
            user_groups.update(user.get_value('groups'))

        # Special case: admins
        if '/config/groups/admins' in user_groups:
            return True

        # 3. Check access rules
        owner = self.get_resource(owner) if owner else self
        for rule in owner.get_resources():
            if rule.get_value('permission') == permission:
                if rule.get_value('group') in user_groups:
                    return resource is None or rule.match_resource(resource)

        return False


    def get_document_types(self):
        return [AccessRule]


    # Views
    class_views = ['browse_content', 'add_rule', 'edit', 'commit_log']
    browse_content = ConfigAccess_Browse()
    add_rule = NewResource_Local(title=MSG(u'Add rule'))



# Register
Configuration.register_plugin(ConfigAccess)
