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
from itools.core import freeze, thingy_lazy_property
from itools.datatypes import Boolean, Tokens, String
from itools.gettext import MSG
from itools.http import get_context
from itools.web import AccessControl as BaseAccessControl
from itools.web import INFO, ERROR, STLForm, ViewField
from itools.xapian import AndQuery, OrQuery, PhraseQuery, StartQuery

# Import from ikaaro
from buttons import RemoveButton
from forms import EmailField, HiddenField, PasswordField, SelectField
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
    username = user.get_name()
    root = resource.get_site_root()
    if root.has_user_role(username, 'admins'):
        return True

    # Global admin?
    root = get_context().get_physical_root()
    return root.has_user_role(username, 'admins')


###########################################################################
# Views
###########################################################################
class RoleAware_BrowseUsers(SearchForm):

    access = 'is_admin'
    title = MSG(u'Browse Members')
    icon = 'userfolder.png'
    description = MSG(u'See the users and their roles.')

    ids = ViewField(required=True)
    ids.datatype = String(multiple=True)

    sort_by = SearchForm.sort_by()
    sort_by.datatype = String(default='login_name')

    search_fields = [
        ('', MSG(u'All Fields')),
        ('username', MSG(u'Login')),
        ('lastname', MSG(u'Last Name')),
        ('firstname', MSG(u'First Name')),
        ('email_domain', MSG(u'Domain'))]


    @thingy_lazy_property
    def all_items(self):
        resource = self.resource
        context = self.context

        # Search
        search_query = PhraseQuery('format', 'user')
        search_field = self.search_field.value
        search_term = self.search_term.value
        if not search_field and search_term:
            or_query = []
            for field, label in self.search_fields:
                if field:
                    or_query.append(StartQuery(field, search_term))
            search_query = AndQuery(search_query, OrQuery(*or_query))
        elif search_field and search_term:
            search_query = AndQuery(search_query,
                                    StartQuery(search_field, search_term))
        results = context.search(search_query)

        # Show only users that belong to this group (FIXME Use the catalog)
        users = []
        roles = resource.get_members_classified_by_role()
        for user in results.get_documents():
            username = user.get_name()
            for role in roles:
                if username in roles[role]:
                    users.append(user)
                    break

        # Ok
        return users


    @thingy_lazy_property
    def items(self):
        resource = self.resource
        context = self.context

        # Sort
        sort_by = self.sort_by.value
        reverse = self.reverse.value
        if sort_by in ('user_id', 'login_name', 'role'):
            key = lambda x: self.get_item_value(x, sort_by)
        elif sort_by == 'account_state':
            key = lambda x: self.get_item_value(x, sort_by)[0].gettext()
        else:
            key = lambda x: getattr(x, sort_by)

        items = sorted(self.all_items, key=key, reverse=reverse)

        # Batch
        start = self.batch_start.value
        size = self.batch_size.value
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


    def get_item_value(self, item, column):
        if column == 'checkbox':
            return item.get_name(), False
        elif column == 'user_id':
            name = item.get_name()
            return name, '/users/%s' % name
        elif column == 'login_name':
            return item.get_value('username')
        elif column == 'firstname':
            return item.get_value('firstname')
        elif column == 'lastname':
            return item.get_value('lastname')
        elif column == 'role':
            name = item.get_name()
            role = self.resource.get_user_role(name)
            role = self.resource.get_role_title(role)
            return role, ';edit_membership?id=%s' % name
        elif column == 'account_state':
            if item.get_value('user_must_confirm'):
                href = '/users/%s/;resend_confirmation' % item.get_name()
                return MSG(u'Resend Confirmation'), href
            return MSG(u'Active'), None


    def action_remove(self):
        context = self.context
        resource = self.resource

        usernames = self.ids.value

        # Verify if after this operation, all is ok
        user = context.user
        if str(user.get_name()) in usernames:
            if not is_admin(user, resource.get_parent()):
                context.message = ERROR(u'You cannot remove yourself.')
                return

        # Make the operation
        resource.set_user_role(usernames, None)

        # Ok
        context.message = u"Members deleted."



class RoleAware_EditMembership(STLForm):

    access = 'is_admin'
    template = 'access/edit_membership_form.xml'

    id = HiddenField(required=True)
    role = SelectField(required=True)


    def name(self):
        return self.context.get_user_title(self.id.value)


    def roles(self):
        return self.resource.get_roles_namespace(self.id.value)


    def action(self):
        context = self.context

        user_id = self.id.value
        role = self.role.value

        # Verify if after this operation, all is ok
        user = context.user
        if str(user.get_name()) == user_id and role != 'admins':
            if not is_admin(user, self.resource.get_parent()):
                context.message = ERROR(u'You cannot degrade your own role.')
                return

        # Make the operation
        self.resource.set_user_role(user_id, role)

        # Ok
        context.message = u"Role updated."
        context.redirect()



class RoleAware_AddUser(STLForm):

    access = 'is_admin'
    title = MSG(u'Add New Member')
    icon = 'card.png'
    description = MSG(u'Grant access to a new user.')
    template = 'access/add_user.xml'

    email = EmailField(required=True)
    role = SelectField(required=True)
    newpass = PasswordField()
    newpass2 = PasswordField()


    def is_admin(self):
        resource = self.resource
        return resource.is_admin(self.context.user, resource)


    def roles(self):
        return self.resource.get_roles_namespace()


    def action(self, resource, context, form):
        users = context.get_resource('users')

        # Check whether the user already exists
        email = form['email'].strip()
        results = context.search(email=email)
        if len(results):
            user = results.get_documents()[0]
        else:
            user = None

        # Get the user (create it if needed)
        if user:
            username = user.get_name()
            # Check the user is not yet in the group
            if username in resource.get_users():
                context.message = ERROR(u'The user is already here.')
                return
        else:
            # New user
            is_admin = resource.is_admin(context.user, resource)
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
            username = user.get_name()
            if password is None:
                # Send confirmation email to activate the account
                user.send_confirmation(context, email)

        # Set the role
        role = form['role']
        resource.set_user_role(username, role)

        # Come back
        if context.has_form_value('add_and_return'):
            return

        goto = '/users/%s/' % username
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


    def is_allowed_to_retire(self, user, resource):
        return self.is_allowed_to_trans(user, resource, 'retire')


    def is_allowed_to_view_folder(self, user, resource):
        index = resource.get_resource('index', soft=True)
        if index is None:
            return False
        return self.is_allowed_to_view(user, index)



class RoleAware(AccessControl):
    """This base class implements access control based on the concept of
    roles.  Includes a user interface.
    """

    class_roles = freeze(['guests', 'members', 'reviewers', 'admins'])

    class_schema = freeze({
        # Metadata
        'website_is_open': Boolean(source='metadata'),
        # Metadata (roles)
        'guests': Tokens(source='metadata', title=MSG(u"Guest")),
        'members': Tokens(source='metadata', title=MSG(u"Member")),
        'reviewers': Tokens(source='metadata', title=MSG(u"Reviewer")),
        'admins': Tokens(source='metadata', title=MSG(u'Admin')),
        # Other
        'users': String(multiple=True, indexed=True)})


    def get_links(self):
        return [ '/users/%s' % x for x in self.get_users() ]


    def get_is_role_aware(self):
        return True


    def get_users(self):
        users = set()
        for rolename in self.get_role_names():
            usernames = self.get_value(rolename)
            users = users.union(usernames)
        return users


    #########################################################################
    # Access Control
    #########################################################################
    def is_allowed_to_view(self, user, resource):
        # Get the variables to resolve the formula
        # Intranet or Extranet
        is_open = self.get_value('website_is_open')
        # The role of the user
        if user is None:
            role = None
        elif self.is_admin(user, resource):
            role = 'admins'
        else:
            role = self.get_user_role(user.get_name())
        # The state of the resource
        if isinstance(resource, WorkflowAware):
            state = resource.get_value('workflow_state')
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
        username = user.get_name()
        if self.has_user_role(username, 'reviewers'):
            return True

        # Members only can touch not-yet-published documents
        if self.has_user_role(username, 'members'):
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
        return self.has_user_role(user.get_name(), 'reviewers', 'members')


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
        username = user.get_name()
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
        return cls.class_schema[name].title


    @classmethod
    def get_role_names(cls):
        """Return the names of the roles available.
        """
        return cls.class_roles


    def get_user_role(self, user_id):
        """Return the role the user has here, or "None" if the user has not
        any role.
        """
        for role in self.get_role_names():
            value = self.get_value(role)
            if value and user_id in value:
                return role
        return None


    def has_user_role(self, user_id, *roles):
        """Return True if the given user has any of the given roles,
        False otherwise.
        """
        for role_name in roles:
            role = self.get_value(role_name)
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
        roles = [ x for x in self.get_role_names() if x != role ]

        # Add the users to the given role
        if role is not None:
            users = self.get_value(role)
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


    def get_members_classified_by_role(self):
        roles = {}
        for rolename in self.get_role_names():
            usernames = self.get_value(rolename)
            roles[rolename] = set(usernames)
        return roles


    #######################################################################
    # User Interface
    #######################################################################
    def get_roles_namespace(self, username=None):
        schema = self.class_schema
        user_role = self.get_user_role(username) if username else None

        return [
            {'name': x, 'title': schema[x].title, 'selected': x == user_role}
            for x in self.class_roles ]


    #######################################################################
    # UI / Views
    #######################################################################
    browse_users = RoleAware_BrowseUsers
    edit_membership = RoleAware_EditMembership
    add_user = RoleAware_AddUser

