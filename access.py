# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Luis Arturo Belmar-Letelier <luis@itaapy.com>
# Copyright (C) 2007 Nicolas Deram <nicolas@itaapy.com>
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
from itools.datatypes import Boolean, Email, Tokens, Unicode, String
from itools.gettext import MSG
from itools.handlers import merge_dicts
from itools.web import AccessControl as BaseAccessControl, STLForm, INFO
from itools.web import ERROR
from itools.xapian import AndQuery, OrQuery, PhraseQuery, StartQuery

# Import from ikaaro
from buttons import RemoveButton
import messages
from views import SearchForm
from workflow import WorkflowAware


###########################################################################
# Utility
###########################################################################
def is_admin(user, resource):
    if user is None or resource is None:
        return False
    # WebSite admin?
    root = resource.get_site_root()
    if root.has_user_role(user.name, 'admins'):
        return True
    # Global admin?
    root = resource.get_root()
    return root.has_user_role(user.name, 'admins')


###########################################################################
# Views
###########################################################################
class RoleAware_BrowseUsers(SearchForm):

    access = 'is_admin'
    title = MSG(u'Browse Members')
    icon = 'userfolder.png'
    description = MSG(u'See the users and their roles.')

    schema = {'ids': String(multiple=True, mandatory=True)}

    def get_query_schema(self):
        return merge_dicts(SearchForm.get_query_schema(self),
                          sort_by=String(default='login_name'))


    search_schema = {
        'search_field': String,
        'search_term': Unicode}

    search_fields = [
        ('', MSG(u'All Fields')),
        ('username', MSG(u'Login')),
        ('lastname', MSG(u'Last Name')),
        ('firstname', MSG(u'First Name'))]


    def get_items(self, resource, context):
        # Search
        search_query = PhraseQuery('format', 'user')
        search_field = context.query['search_field']
        search_term = context.query['search_term'].strip()
        if not search_field and search_term:
            or_query = []
            for field, label in self.get_search_fields(resource, context):
                if field:
                    or_query.append(StartQuery(field, search_term))
            search_query = AndQuery(search_query, OrQuery(*or_query))
        elif search_field and search_term:
            search_query = AndQuery(search_query,
                                    StartQuery(search_field, search_term))
        results = context.root.search(search_query)

        # Show only users that belong to this group (FIXME Use the catalog)
        users = []
        roles = resource.get_members_classified_by_role()
        for user in results.get_documents():
            for role in roles:
                if user.name in roles[role]:
                    users.append(user)
                    break

        # Ok
        return users


    def sort_and_batch(self, resource, context, items):
        # Sort
        sort_by = context.query['sort_by']
        reverse = context.query['reverse']
        if sort_by in ('user_id', 'login_name', 'role'):
            f = lambda x: self.get_item_value(resource, context, x, sort_by)
        elif sort_by == 'account_state':
            f = lambda x: self.get_item_value(resource, context, x,
                                              sort_by)[0].gettext()
        else:
            f = lambda x: getattr(x, sort_by)

        items.sort(cmp=lambda x,y: cmp(f(x), f(y)), reverse=reverse)
        # Batch
        start = context.query['batch_start']
        size = context.query['batch_size']
        return items[start:start+size]


    table_columns = [
        ('checkbox', None),
        ('user_id', MSG(u'User ID')),
        ('login_name', MSG(u'Login')),
        ('firstname', MSG(u'First Name')),
        ('lastname', MSG(u'Last Name')),
        ('role', MSG(u'Role')),
        ('account_state', MSG(u'State'))]


    table_actions = [RemoveButton]


    def get_item_value(self, resource, context, item, column):
        if column == 'checkbox':
            return item.name, False
        elif column == 'user_id':
            return item.name, '/users/%s' % item.name
        elif column == 'login_name':
            return item.username
        elif column == 'firstname':
            return item.firstname
        elif column == 'lastname':
            return item.lastname
        elif column == 'role':
            role = resource.get_user_role(item.name)
            role = resource.get_role_title(role)
            return role, ';edit_membership?id=%s' % item.name
        elif column == 'account_state':
            user = context.root.get_resource(item.abspath)
            if user.get_property('user_must_confirm'):
                href = '/users/%s/;resend_confirmation' % item.name
                return MSG(u'Resend Confirmation'), href
            return MSG(u'Active'), None


    def action_remove(self, resource, context, form):
        usernames = form['ids']

        # Verify if after this operation, all is ok
        user = context.user
        if str(user.name) in usernames:
            if not is_admin(user, resource.parent):
                context.message = ERROR(u'You cannot remove yourself.')
                return

        # Make the operation
        resource.set_user_role(usernames, None)

        # Ok
        context.message = u"Members deleted."



class RoleAware_EditMembership(STLForm):

    access = 'is_admin'
    template = '/ui/access/edit_membership_form.xml'
    schema = {
        'id': String(mandatory=True),
        'role': String(mandatory=True)}


    def get_namespace(self, resource, context):
        user_id = context.get_form_value('id')
        user = resource.get_resource('/users/%s' % user_id)

        return {
            'id': user_id,
            'name': user.get_title(),
            'roles': resource.get_roles_namespace(user_id)}


    def action(self, resource, context, form):
        user_id = form['id']
        role = form['role']

        # Verify if after this operation, all is ok
        user = context.user
        if str(user.name) == user_id and role != 'admins':
            if not is_admin(user, resource.parent):
                context.message = ERROR(u'You cannot degrade your own role.')
                return

        # Make the operation
        resource.set_user_role(user_id, role)

        # Ok
        context.message = u"Role updated."



class RoleAware_AddUser(STLForm):

    access = 'is_admin'
    title = MSG(u'Add New Member')
    icon = 'card.png'
    description = MSG(u'Grant access to a new user.')
    template = '/ui/access/add_user.xml'
    schema = {
        'email': Email(mandatory=True),
        'role': String(mandatory=True),
        'newpass': String,
        'newpass2': String}


    def get_namespace(self, resource, context):
        return {
            'is_admin': resource.is_admin(context.user, resource),
            'roles': resource.get_roles_namespace()}


    def action(self, resource, context, form):
        root = context.root
        user = context.user
        users = root.get_resource('users')

        # Check whether the user already exists
        email = form['email']
        results = root.search(email=email)
        if results.get_n_documents():
            user_id = results.get_documents()[0].name
        else:
            user_id = None

        # Get the user (create it if needed)
        if user_id is None:
            # New user
            is_admin = resource.is_admin(user, resource)
            if is_admin:
                password = form['newpass']
                password2 = form['newpass2']
                # Check the password is right
                if password != password2:
                    context.message = messages.MSG_PASSWORD_MISMATCH
                    return
                if not password:
                    # Admin can set no password
                    # so the user must activate its account
                    password = None
            else:
                password = None
            # Add the user
            user = users.set_user(email, password)
            user_id = user.name
            if password is None:
                # Send confirmation email to activate the account
                user.send_confirmation(context, email)
        else:
            user = users.get_resource(user_id)
            # Check the user is not yet in the group
            members = resource.get_members()
            if user_id in members:
                context.message = ERROR(u'The user is already here.')
                return

        # Set the role
        role = form['role']
        resource.set_user_role(user_id, role)

        # Come back
        if context.has_form_value('add_and_return'):
            return

        goto = '/users/%s/' % user.name
        message = INFO(u'User added.')
        return context.come_back(message, goto=goto)



###########################################################################
# Model
###########################################################################
class AccessControl(BaseAccessControl):

    def is_admin(self, user, resource):
        return is_admin(user, resource)


    def is_allowed_to_view(self, user, resource):
        # Resources with workflow
        if isinstance(resource, WorkflowAware):
            state = resource.workflow_state
            # Anybody can see public resources
            if state == 'public':
                return True

            # Only those who can edit are allowed to see non-public resources
            return self.is_allowed_to_edit(user, resource)

        # Everybody can see resources without workflow
        return True


    def is_allowed_to_edit(self, user, resource):
        # By default only the admin can touch stuff
        return self.is_admin(user, resource)


    # By default all other change operations (add, remove, copy, etc.)
    # are equivalent to "edit".
    def is_allowed_to_lock(self, user, resource):
        return self.is_allowed_to_edit(user, resource)


    def is_allowed_to_add(self, user, resource):
        return self.is_allowed_to_edit(user, resource)


    def is_allowed_to_remove(self, user, resource):
        return self.is_allowed_to_edit(user, resource)


    def is_allowed_to_copy(self, user, resource):
        return self.is_allowed_to_edit(user, resource)


    def is_allowed_to_move(self, user, resource):
        return self.is_allowed_to_edit(user, resource)


    def is_allowed_to_trans(self, user, resource, name):
        if not isinstance(resource, WorkflowAware):
            return False

        return self.is_allowed_to_edit(user, resource)


    def is_allowed_to_publish(self, user, resource):
        return self.is_allowed_to_trans(user, resource, 'publish')


    def is_allowed_to_view_folder(self, user, resource):
        try:
            index = resource.get_resource('index')
        except LookupError:
            return False
        return self.is_allowed_to_view(user, index)



class RoleAware(AccessControl):
    """This base class implements access control based on the concept of
    roles.  Includes a user interface.
    """

    # To override
    __roles__ = [
        {'name': 'guests', 'title': MSG(u"Guest")},
        {'name': 'members', 'title': MSG(u"Member")},
        {'name': 'reviewers', 'title': MSG(u"Reviewer")},
        {'name': 'admins', 'title': MSG(u'Admin')},
    ]


    @classmethod
    def get_metadata_schema(cls):
        schema = {}
        for rolename in cls.get_role_names():
            schema[rolename] = Tokens(default=())
        schema['website_is_open'] = Boolean
        return schema


    def get_links(self):
        return [ '/users/%s' % x for x in self.get_members() ]


    #########################################################################
    # Access Control
    #########################################################################
    def is_allowed_to_view(self, user, resource):
        # Get the variables to resolve the formula
        # Intranet or Extranet
        is_open = self.get_property('website_is_open')
        # The role of the user
        if user is None:
            role = None
        elif self.is_admin(user, resource):
            role = 'admins'
        else:
            role = self.get_user_role(user.name)
        # The state of the resource
        if isinstance(resource, WorkflowAware):
            state = resource.workflow_state
        else:
            state = 'public'

        # The formula
        # Extranet
        if is_open:
            if state == 'public':
                return True
            return role is not None
        # Intranet
        if role in ('admins', 'reviewers', 'members'):
            return True
        elif role == 'guests':
            return state == 'public'
        return False


    def is_allowed_to_edit(self, user, resource):
        # Anonymous can touch nothing
        if user is None:
            return False

        # Admins are all powerfull
        if self.is_admin(user, resource):
            return True

        # Reviewers too
        if self.has_user_role(user.name, 'reviewers'):
            return True

        # Members only can touch not-yet-published documents
        if self.has_user_role(user.name, 'members'):
            if isinstance(resource, WorkflowAware):
                state = resource.workflow_state
                # Public resources are frozen for members
                if state != 'public':
                    return True

        return False


    def is_allowed_to_add(self, user, resource):
        # Anonymous can touch nothing
        if user is None:
            return False

        # Admins are all powerfull
        if self.is_admin(user, resource):
            return True

        # Reviewers too
        return self.has_user_role(user.name, 'reviewers', 'members')


    def is_allowed_to_trans(self, user, resource, name):
        if not isinstance(resource, WorkflowAware):
            return False

        # Anonymous can touch nothing
        if user is None:
            return False

        # Admins are all powerfull
        if self.is_admin(user, resource):
            return True

        # Reviewers can do everything
        username = user.name
        if self.has_user_role(username, 'reviewers'):
            return True

        # Members only can request and retract
        if self.has_user_role(username, 'members'):
            return name in ('request', 'unrequest')

        return False


    #########################################################################
    # API / Public
    #########################################################################
    @classmethod
    def get_role_title(cls, name):
        for role in cls.__roles__:
            if role['name'] == name:
                return role['title']
        return None


    @classmethod
    def get_role_names(cls):
        """Return the names of the roles available.
        """
        return [ r['name'] for r in cls.__roles__ ]


    def get_user_role(self, user_id):
        """Return the role the user has here, or "None" if the user has not
        any role.
        """
        for role in self.get_role_names():
            value = self.get_property(role)
            if (value is not None) and (user_id in value):
                return role
        return None


    def has_user_role(self, user_id, *roles):
        """Return True if the given user has any of the given roles,
        False otherwise.
        """
        for role_name in roles:
            role = self.get_property(role_name)
            if role and user_id in role:
                return True
        return False


    def set_user_role(self, user_ids, role):
        """Sets the role for the given users. If "role" is None, removes the
        role of the users.
        """
        # The input parameter "user_ids" should be a list
        if isinstance(user_ids, str):
            user_ids = [user_ids]
        elif isinstance(user_ids, unicode):
            user_ids = [str(user_ids)]

        # Change "user_ids" to a set, to simplify the rest of the code
        user_ids = set(user_ids)

        # Build the list of roles from where the users will be removed
        roles = self.get_role_names()
        if role is not None:
            roles.remove(role)

        # Add the users to the given role
        if role is not None:
            users = self.get_property(role)
            users = set(users)
            if user_ids - users:
                users = tuple(users | user_ids)
                self.set_property(role, users)

        # Remove the user from the other roles
        for role in roles:
            users = self.get_property(role)
            users = set(users)
            if users & user_ids:
                users = tuple(users - user_ids)
                self.set_property(role, users)


    def get_members(self):
        members = set()
        for rolename in self.get_role_names():
            usernames = self.get_property(rolename)
            members = members.union(usernames)
        return members


    def get_members_classified_by_role(self):
        roles = {}
        for rolename in self.get_role_names():
            usernames = self.get_property(rolename)
            roles[rolename] = set(usernames)
        return roles


    #######################################################################
    # User Interface
    #######################################################################
    def get_roles_namespace(self, username=None):
        # Build a list with the role name and title
        namespace = [ x.copy() for x in self.__roles__ ]

        # If a username was not given, we are done
        if username is None:
            return namespace

        # Add the selected field
        user_role = self.get_user_role(username)
        for role in namespace:
            role['selected'] = (user_role == role['name'])

        return namespace


    #######################################################################
    # UI / Views
    #######################################################################
    browse_users = RoleAware_BrowseUsers()
    edit_membership = RoleAware_EditMembership()
    add_user = RoleAware_AddUser()
