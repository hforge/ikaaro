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
from itools.core import freeze, is_prototype, proto_property
from itools.database import AllQuery, AndQuery, OrQuery, PhraseQuery
from itools.datatypes import Enumerate
from itools.gettext import MSG
from itools.uri import Path
from itools.web import get_context

# Import from ikaaro
from autoadd import AutoAdd
from autoedit import AutoEdit
from buttons import Remove_BrowseButton
from config import Configuration
from config_common import NewResource_Local
from enumerates import Groups_Datatype
from fields import Select_Field
from folder import Folder
from folder_views import Folder_BrowseContent
from resource_ import DBResource
from utils import get_base_path_query


###########################################################################
# Fields & datatypes
###########################################################################
class Path_Datatype(Enumerate):

    def get_options(self):
        context = get_context()

        items = []
        for doc in context.search(base_classes='folder').get_documents():
            path = Path(doc.abspath)
            title = '/' if not path else ('%s/' % path)
            items.append({'name': path, 'value': title, 'selected': False})

        items.sort(key=lambda x: x['value'])
        return items


class Path_Field(Select_Field):

    datatype = Path_Datatype
    has_empty_option = False
    title = MSG(u'Path')



class PathDepth_Field(Select_Field):

    title = MSG(u'Depth')
    default = '0'
    multiple = False
    has_empty_option = False
    endline = True

    options = [
        {'name': '0', 'value': u'0'},
        {'name': '1', 'value': u'1'},
        {'name': '2', 'value': u'2'},
        {'name': '3', 'value': u'3'},
        {'name': '4', 'value': u'4'},
        {'name': '5', 'value': u'5'},
        {'name': '*', 'value': MSG(u'No limit')}]



class Permission_Datatype(Enumerate):

    options = [
        {'name': 'view', 'value': MSG(u'View')},
        {'name': 'edit', 'value': MSG(u'Remove and modify')},
        {'name': 'share', 'value': MSG(u'Share')},
        {'name': 'add', 'value': MSG(u'Add')}]


class Permissions_Field(Select_Field):

    title = MSG(u'Permission')
    datatype = Permission_Datatype


class SearchFormat_Datatype(Enumerate):

    @classmethod
    def get_options(self):
        database = get_context().database

        options = {}
        for cls in database.get_resource_classes():
            options.setdefault(cls.class_id, cls)

        options = [ {'name': class_id, 'value': cls.class_title.gettext()}
                    for class_id, cls in options.items() ]

        options.sort(key=lambda x: x['value'])
        return options


class SearchFormat_Field(Select_Field):

    title = MSG(u'Resource type')
    datatype = SearchFormat_Datatype



###########################################################################
# Access rule
###########################################################################
class AccessRule_Results(Folder_BrowseContent):

    title = MSG(u'View results')
    search_schema = {}
    search_widgets = []

    def get_items_query(self, resource, context):
        return resource.get_search_query()


class AccessRule(DBResource):

    class_id = 'config-access-rule'
    class_title = MSG(u'Access rule')

    # Fields
    group = Select_Field(required=True, title=MSG(u'User group'),
                         datatype=Groups_Datatype, indexed=True, stored=True)
    permission = Permissions_Field(required=True, indexed=True, stored=True)
    search_path = Path_Field(indexed=True, stored=True)
    search_path_depth = PathDepth_Field()
    search_format = SearchFormat_Field(indexed=True, stored=True)

    # Views
    class_views = ['edit', 'results', 'commit_log']
    _fields = ['group', 'permission', 'search_path', 'search_path_depth',
               'search_format']
    new_instance = AutoAdd(fields=_fields, automatic_resource_name=True)
    edit = AutoEdit(fields=_fields)
    results = AccessRule_Results

    # API
    def get_search_query(self):
        permission = self.get_value('permission')
        if permission == 'add':
            names = ['path']
        else:
            names = ['path', 'format']

        # Query
        query = AndQuery()
        for name in names:
            field_name = 'search_%s' % name
            field = self.get_field(field_name)
            value = field.get_value(self, field_name)
            if not value:
                continue

            if name == 'path':
                depth = self.get_value('search_path_depth')
                depth = None if depth == '*' else int(depth)
                subquery = get_base_path_query(value, 0, depth)
            elif field.multiple:
                err = "access rules don't yet support multiple fields"
                raise NotImplementedError, err
            else:
                subquery = PhraseQuery(name, value)

            query.append(subquery)

        # Ok
        return query



###########################################################################
# Configuration module
###########################################################################
class ConfigAccess_Browse(Folder_BrowseContent):

    query_schema = Folder_BrowseContent.query_schema.copy()
    query_schema['sort_by'] = query_schema['sort_by'](default='abspath')
    query_schema['reverse'] = query_schema['reverse'](default=False)

    # Search form
    _columns = ['group', 'permission', 'search_path', 'search_format']

    @proto_property
    def _search_fields(self):
        cls = AccessRule
        for name in self._columns:
            yield name, cls.get_field(name)


    @proto_property
    def search_widgets(self):
        widgets = []
        for name, field in self._search_fields:
            if is_prototype(field, Select_Field):
                widget = field.widget
                widgets.append(
                    widget(name, has_empty_option=True, title=field.title))
        return widgets


    @proto_property
    def search_schema(self):
        schema = {}
        for name, field in self._search_fields:
            if is_prototype(field, Select_Field):
                schema[name] = field.datatype(default=None)
        return schema


    @proto_property
    def table_columns(self):
        columns = [
            ('checkbox', None),
            ('abspath', MSG(u'Num.'))]
        for name, field in self._search_fields:
            columns.append((name, field.title))

        return columns

    table_actions = [Remove_BrowseButton]


    def get_key_sorted_by_abspath(self):
        def key(item):
            return int(item.name)
        return key


    def get_key_sorted_by_group(self):
        def key(item, cache={}):
            title = Groups_Datatype.get_value(item.group)
            if is_prototype(title, MSG):
                title = title.gettext()
            return title.lower()
        return key


    def get_item_value(self, resource, context, item, column):
        if column == 'search_path':
            path = item.get_value('search_path')
            if not path or not resource.get_resource(path, soft=True):
                return None

            depth = item.get_value('search_path_depth')
            if depth == '0':
                title = path
            else:
                title = '%s (%s)' % (path, depth)

            return title, path

        proxy = super(ConfigAccess_Browse, self)
        value = proxy.get_item_value(resource, context, item, column)

        if column == 'group':
            group = item.get_value('group')
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
    _everything = freeze({'path': '/', 'path_depth': '*'})
    default_rules = [
        # Everybody can see the theme
        ('everybody', 'view', {'path': '/config/theme', 'path_depth': '*'}),
        # Authenticated users can see any content
        ('authenticated', 'view', _everything),
        # Members can add new content and edit private content
        ('/config/groups/members', 'add', _everything),
        ('/config/groups/members', 'edit', _everything),
        # Reviewers can add new content, edit any content and publish
        ('/config/groups/reviewers', 'add', _everything),
        ('/config/groups/reviewers', 'edit', _everything),
        ('/config/groups/reviewers', 'share', _everything)]

    def init_resource(self, **kw):
        super(ConfigAccess, self).init_resource(**kw)
        # Access rules
        rules = self.default_rules
        for group, permission, kw in rules:
            rule = self.make_resource(None, AccessRule, group=group)
            rule.set_value('permission', permission)
            for key in kw:
                rule.set_value('search_%s' % key, kw[key])


    # API
    def _get_user_groups(self, user):
        user_groups = set(['everybody'])
        if user:
            user_groups.add('authenticated')
            user_groups.update(user.get_value('groups'))

        return user_groups, '/config/groups/admins' in user_groups


    def get_search_query(self, user, permission, class_id=None):
        # Special case: admins can see everything
        user_groups, is_admin = self._get_user_groups(user)
        if is_admin:
            return AllQuery()

        # 1. Back-office access rules
        rules_query = OrQuery()
        for rule in self.get_resources():
            if rule.get_value('permission') != permission:
                continue

            if rule.get_value('group') not in user_groups:
                continue

            if permission == 'add':
                r_format = rule.get_value('search_format')
                if class_id and r_format and class_id != r_format:
                    continue

            rules_query.append(rule.get_search_query())

        # Case: anonymous
        if not user:
            return AndQuery(rules_query, PhraseQuery('share', 'everybody'))

        # Case: authenticated
        share_query = OrQuery(*[ PhraseQuery('share', x)
                                 for x in user_groups ])
        share_query.append(PhraseQuery('share', str(user.abspath)))
        query = AndQuery(rules_query, share_query)

        if permission != 'share':
            return OrQuery(PhraseQuery('owner', str(user.abspath)), query)

        return query


    def has_permission(self, user, permission, resource, class_id=None):
        # The query
        query = AndQuery(
            self.get_search_query(user, permission, class_id),
            PhraseQuery('abspath', str(resource.abspath)))

        # Search
        results = get_context().search(query)
        return len(results) > 0


    def get_document_types(self):
        return [AccessRule]


    # Views
    class_views = ['browse_content', 'add_rule', 'edit', 'commit_log']
    browse_content = ConfigAccess_Browse
    add_rule = NewResource_Local(title=MSG(u'Add rule'))



# Register
Configuration.register_module(ConfigAccess)
