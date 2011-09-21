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
from itools.core import is_prototype, proto_property
from itools.database import AllQuery, AndQuery, OrQuery, PhraseQuery
from itools.datatypes import Enumerate
from itools.gettext import MSG
from itools.web import get_context

# Import from ikaaro
from autoedit import AutoEdit
from autoform import SelectWidget
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

        items.sort(key=lambda x: x['value'])
        return items


class Path_Field(Select_Field):

    datatype = Path_Datatype
    has_empty_option = False
    title = MSG(u'Path')



###########################################################################
# Access rule
###########################################################################
class Permission_Datatype(Enumerate):

    options = [
        {'name': 'view', 'value': MSG(u'View')},
        {'name': 'edit', 'value': MSG(u'Remove and modify')},
        {'name': 'add', 'value': MSG(u'Add')},
        {'name': 'change_state', 'value': MSG(u'Change workflow state')}]


class Permissions_Field(Select_Field):

    title = MSG(u'Permission')
    datatype = Permission_Datatype



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
                         datatype=UserGroupsDatatype,
                         indexed=True, stored=True)
    permission = Permissions_Field(required=True, indexed=True, stored=True)
    search_state = State_Field(has_empty_option=True, default='',
                               indexed=True, stored=True)
    search_parent_paths = Path_Field(indexed=True, stored=True)

    # Views
    class_views = ['edit', 'results', 'commit_log']
    _fields = ['group', 'permission', 'search_state', 'search_parent_paths']
    new_instance = NewInstance_Local(fields=_fields,
                                     automatic_resource_name=True)
    edit = AutoEdit(fields=_fields)
    results = AccessRule_Results()

    # API
    def get_search_query(self):
        query = AndQuery()
        for name in self.fields:
            if not name.startswith('search_'):
                continue
            value = self.get_value(name)
            if not value:
                continue

            field = self.get_field(name)
            if not field.multiple:
                value = [value]

            name = name[7:]
            subquery = OrQuery()
            for value in value:
                subquery.append(PhraseQuery(name, value))
                # Special case: parent_paths
                if name == 'parent_paths':
                    subquery.append(PhraseQuery('abspath', value))

            if len(subquery.atoms) == 1:
                subquery = subquery.atoms[0]

            query.append(subquery)

        query.append(PhraseQuery('is_content', True))
        return query



###########################################################################
# Configuration module
###########################################################################
class ConfigAccess_Browse(Folder_BrowseContent):

    query_schema = Folder_BrowseContent.query_schema.copy()
    query_schema['sort_by'] = query_schema['sort_by'](default='abspath')
    query_schema['reverse'] = query_schema['reverse'](default=False)

    # Search form
    @proto_property
    def search_widgets(self):
        cls = AccessRule
        return [
            SelectWidget('group', title=cls.group.title),
            SelectWidget('permission', title=cls.permission.title),
            SelectWidget('search_state', title=cls.search_state.title),
            SelectWidget('search_parent_paths',
                         title=cls.search_parent_paths.title)]


    @proto_property
    def search_schema(self):
        cls = AccessRule
        return {
            'group': cls.group.datatype,
            'permission': cls.permission.datatype,
            'search_state': cls.search_state.datatype(default=None),
            'search_parent_paths': cls.search_parent_paths.datatype}


    @proto_property
    def table_columns(self):
        cls = AccessRule
        return [
            ('checkbox', None),
            ('abspath', MSG(u'Num.')),
            ('group', cls.group.title),
            ('permission', cls.permission.title),
            ('search_state', cls.search_state.title),
            ('search_parent_paths', cls.search_parent_paths.title)]

    table_actions = [RemoveButton]


    def get_key_sorted_by_group(self):
        def key(item, cache={}):
            title = UserGroupsDatatype.get_value(item.group)
            if is_prototype(title, MSG):
                title = title.gettext()
            return title.lower()
        return key


    def get_item_value(self, resource, context, item, column):
        if column == 'search_parent_paths':
            brain, item_resource = item
            value = brain.search_parent_paths
            if value:
                resource = resource.get_resource(value, soft=True)
                if resource:
                    return value, value
            return value

        proxy = super(ConfigAccess_Browse, self)
        value = proxy.get_item_value(resource, context, item, column)

        if column == 'group':
            brain, item_resource = item
            group = brain.group
            if group[0] == '/':
                return value, group

        return value



class ConfigAccess(Folder):

    class_id = 'config-access'
    class_version = '20110606'
    class_title = MSG(u'Access Control')
    class_description = MSG(u'Choose the security policy.')
    class_icon48 = 'icons/48x48/lock.png'

    # Configuration
    config_name = 'access'
    config_group = 'access'

    # Initialization
    default_rules = [
        # Authenticated users can see any content
        ('authenticated', 'view', None, None),
        # Members can add new content, edit private content and request
        # publication
        ('/config/groups/members', 'add', None, None),
        ('/config/groups/members', 'edit', 'private', None),
        # Reviewers can add new content, edit any content and publish
        ('/config/groups/reviewers', 'add', None, None),
        ('/config/groups/reviewers', 'edit', None, None),
        ('/config/groups/reviewers', 'change_state', None, None)]

    def init_resource(self, **kw):
        super(ConfigAccess, self).init_resource(**kw)
        # Access rules
        for group, permission, state, path in self.default_rules:
            rule = self.make_resource(None, AccessRule, group=group,
                                      permission=permission)
            rule.set_value('search_state', state)
            rule.set_value('search_parent_paths', path)


    # API
    def _get_user_groups(self, user):
        user_groups = set(['everybody'])
        if user:
            user_groups.add('authenticated')
            user_groups.update(user.get_value('groups'))

        return user_groups, '/config/groups/admins' in user_groups


    def get_search_query(self, user, permission):
        # Special case: admins can see everything
        user_groups, is_admin = self._get_user_groups(user)
        if is_admin:
            return AllQuery()

        # Build the query
        # 1. Ownership
        query = OrQuery()
        if user:
            query.append(PhraseQuery('owner', str(user.abspath)))

        # Access rules
        for rule in self.get_resources():
            if rule.get_value('permission') == permission:
                if rule.get_value('group') in user_groups:
                    query.append(rule.get_search_query())

        return query


    def has_permission(self, user, permission, resource=None):
        # Case 1: we got a resource
        if resource:
            query = AndQuery(
                self.get_search_query(user, permission),
                PhraseQuery('abspath', str(resource.abspath)))
            results = get_context().search(query)
            return len(results) > 0

        # Case 2: no resource
        # Special case: admins
        user_groups, is_admin = self._get_user_groups(user)
        if is_admin:
            return True

        # Access rules
        for rule in self.get_resources():
            if rule.get_value('permission') == permission:
                if rule.get_value('group') in user_groups:
                    return True

        return False


    def get_document_types(self):
        return [AccessRule]


    # Views
    class_views = ['browse_content', 'add_rule', 'edit', 'commit_log']
    browse_content = ConfigAccess_Browse()
    add_rule = NewResource_Local(title=MSG(u'Add rule'))



# Register
Configuration.register_plugin(ConfigAccess)
