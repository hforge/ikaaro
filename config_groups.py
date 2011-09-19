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
from itools.core import proto_lazy_property
from itools.datatypes import Enumerate, String
from itools.gettext import MSG
from itools.web import get_context

# Import from ikaaro
from buttons import BrowseButton, RemoveButton, RenameButton
from config import Configuration
from config_common import NewResource_Local, NewInstance_Local
from folder import Folder, Folder_BrowseContent
from messages import MSG_CHANGES_SAVED
from resource_ import DBResource
from user_views import BrowseUsers



class UserGroupsDatatype(Enumerate):

    special_groups = [
        {'name': 'everybody', 'value': MSG(u'Everybody')},
        {'name': 'authenticated', 'value': MSG(u'Authenticated')}]

    def get_options(self):
        config = get_context().root.get_resource('config')
        groups = [ {'name': str(group.abspath), 'value': group.get_title()}
                   for group in config.get_resources('groups') ]

        # Special groups
        if self.special_groups:
            return self.special_groups + groups

        return groups



class Group_BrowseUsers(BrowseUsers):

    schema = {'ids': String(multiple=True)}

    table_columns = [
        ('checkbox', None),
        ('user_id', MSG(u'User ID')),
        ('login_name', MSG(u'Login')),
        ('firstname', MSG(u'First Name')),
        ('lastname', MSG(u'Last Name')),
        ('account_state', MSG(u'State'))]
    table_actions = [
        BrowseButton(access='is_admin', title=MSG(u'Update'))]


    @proto_lazy_property
    def _property_name(self):
        return self.resource.parent.property_name


    def get_item_value(self, resource, context, item, column):
        if column == 'checkbox':
            user = context.root.get_resource(item.abspath)
            groups = user.get_value(self._property_name)
            return item.name, str(resource.abspath) in groups

        proxy = super(Group_BrowseUsers, self)
        return proxy.get_item_value(resource, context, item, column)


    def action(self, resource, context, form):
        group_id = str(resource.abspath)

        root = resource.get_resource('/')
        for user in root.get_resources('users'):
            groups = set(user.get_value(self._property_name))
            if user.name in form['ids']:
                groups.add(group_id)
            else:
                groups.discard(group_id)
            user.set_value(self._property_name, list(groups))

        context.message = MSG_CHANGES_SAVED



class Group(DBResource):

    class_id = 'config-group'
    class_title = MSG(u'User Group')
    class_description = MSG(u'...')

    # Views
    class_views = ['browse_users', 'edit']
    browse_users = Group_BrowseUsers()
    new_instance = NewInstance_Local()



class BrowseGroups(Folder_BrowseContent):

    access = 'is_admin'
    title = MSG(u'Browse groups')

    search_schema = {}
    search_widgets = []

    table_columns = [
        ('checkbox', None),
        ('abspath', MSG(u'Name')),
        ('title', MSG(u'Title')),
        ('members', MSG(u'Members')),
        ('mtime', MSG(u'Last Modified')),
        ('last_author', MSG(u'Last Author'))]
    table_actions = [RemoveButton, RenameButton]

    @proto_lazy_property
    def _property_name(self):
        return self.resource.property_name


    def get_item_value(self, resource, context, item, column):
        if column == 'members':
            brain, item_resource = item
            kw = {self._property_name: brain.abspath}
            results = context.search(format='user', **kw)
            return len(results)

        proxy = super(BrowseGroups, self)
        return proxy.get_item_value(resource, context, item, column)



class ConfigGroups(Folder):

    class_id = 'config-groups'
    class_title = MSG(u'User Groups')
    class_description = MSG(u'Manage user groups.')
    class_icon48 = 'icons/48x48/groups.png'

    # Configuration
    config_name = 'groups'
    config_group = 'access'
    property_name = 'groups'

    # Views
    class_views = ['browse_content', 'add_group', 'edit', 'commit_log']
    browse_content = BrowseGroups()
    add_group = NewResource_Local(title=MSG(u'Add group'))

    default_groups = [
        ('admins', {'en': u'Admins'}),
        ('reviewers', {'en': u'Reviewers'}),
        ('members', {'en': u'Members'})]


    def init_resource(self, **kw):
        super(ConfigGroups, self).init_resource(**kw)
        # Add default groups
        for name, title in self.default_groups:
            self.make_resource(name, Group, title=title)


    def get_document_types(self):
        return [Group]


Configuration.register_plugin(ConfigGroups)
