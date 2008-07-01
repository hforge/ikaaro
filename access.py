# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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

# Import from the Standard Library
from operator import itemgetter

# Import from itools
from itools.datatypes import Boolean, Email, Integer, Tokens, Unicode, String
from itools.gettext import MSG
from itools.stl import stl
from itools.uri import get_reference
from itools.web import AccessControl as BaseAccessControl, STLForm

# Import from ikaaro
from messages import *
from views import BrowseForm
import widgets
from workflow import WorkflowAware


###########################################################################
# Views
###########################################################################
class PermissionsForm(BrowseForm):

    access = 'is_admin'
    __label__ = MSG(u"Control Panel", __name__)
    title = u"Browse Members"
    description = u"See the users and their roles."
    icon = 'userfolder.png'

    query_schema = {
        'search_field': String,
        'search_term': Unicode,
        'sortorder': String(default='up'),
        'sortby': String(multiple=True, default=['login_name']),
        'batchstart': Integer(default=0),
    }

    schema = {
        'ids': String(multiple=True, mandatory=True),
    }

    search_fields = [
        ('username', u'Login'),
        ('lastname', u'Last Name'),
        ('firstname', u'First Name')]


    def get_namespace(self, model, context, query):
        namespace = {}

        gettext = model.gettext

        # Get values from the request
        sortby = query['sortby']
        sortorder = query['sortorder']
        start = query['batchstart']
        size = 20

        # Search
        field = query['search_field']
        term = query['search_term']
        term = term.strip()
        search_query = {'format': 'user'}
        if field:
            query[field] = term
        root = context.root
        results = root.search(**search_query)

        roles = model.get_members_classified_by_role()

        # Build the namespace
        members = []
        for user in results.get_documents():
            user_id = user.name
            # Find out the user role. Skip the user if does not belong to
            # this group
            for role in roles:
                if user_id in roles[role]:
                    break
            else:
                continue
            # Build the namespace for the user
            ns = {}
            ns['checkbox'] = True
            ns['id'] = user_id
            ns['img'] = None
            # Email
            href = '/users/%s' % user_id
            ns['user_id'] = int(user_id), href
            # Title
            ns['login_name'] = user.username
            ns['firstname'] = user.firstname
            ns['lastname'] = user.lastname
            # Role
            role = model.get_role_title(role)
            href = ';edit_membership?id=%s' % user_id
            ns['role'] = role, href
            # State
            user_object = root.get_object(user.abspath)
            if user_object.get_property('user_must_confirm'):
                account_state = (gettext(u'Inactive'),
                                 '/users/%s/;resend_confirmation' % user_id)
            else:
                account_state = gettext(u'Active')
            ns['account_state'] = account_state
            # Append
            members.append(ns)

        # Sort
        members.sort(key=itemgetter(sortby[0]), reverse=sortorder=='down')

        # Batch
        total = len(members)
        members = members[start:start+size]

        # The columns
        columns = [('user_id', u'User ID'),
                   ('login_name', u'Login'),
                   ('firstname', u'First Name'),
                   ('lastname', u'Last Name'),
                   ('role', u'Role'),
                   ('account_state', u'State')]
        columns = [ (name, gettext(__name__, title))
                    for name, title in columns ]

        # The actions
        actions = [('permissions_del_members', gettext(u'Delete'),
                   'button_delete', None)]

        namespace['batch'] = widgets.batch(context.uri, start, size, total)
        namespace['table'] = widgets.table(columns, members, sortby, sortorder,
                                           actions, gettext)

        return namespace


    def permissions_del_members(self, model, context, form):
        usernames = form['ids']
        model.set_user_role(usernames, None)
        # Ok
        context.message = u"Members deleted."



class MembershipForm(STLForm):

    access = 'is_admin'
    template = '/ui/access/edit_membership_form.xml'
    schema = {
        'id': String(mandatory=True),
        'role': String(mandatory=True),
    }


    def get_namespace(self, model, context):
        user_id = context.get_form_value('id')
        user = model.get_object('/users/%s' % user_id)

        return {
            'id': user_id,
            'name': user.get_title(),
            'roles': model.get_roles_namespace(user_id),
        }


    def action(self, model, context, form):
        user_id = form['id']
        role = form['role']

        model.set_user_role(user_id, role)
        # Ok
        context.message = u"Role updated."



class NewUserForm(STLForm):

    access = 'is_admin'
    __label__ = MSG(u'Control Panel', __name__)
    title = u'Add New Member'
    description = u'Grant access to a new user.'
    icon = 'card.png'
    template = '/ui/access/new_user.xml'
    schema = {
        'email': Email(mandatory=True),
        'role': String(mandatory=True),
        'newpass': String,
        'newpass2': String,
    }


    def get_namespace(self, model, context):
        return {
            'is_admin': model.is_admin(context.user, model),
            'roles': model.get_roles_namespace(),
        }


    def action(self, model, context, form):
        root = context.root
        user = context.user
        users = root.get_object('users')

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
            is_admin = model.is_admin(user, model)
            if is_admin:
                password = form['newpass']
                password2 = form['newpass2']
                # Check the password is right
                if password != password2:
                    context.message = MSG_PASSWORD_MISMATCH
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
            user = users.get_object(user_id)
            # Check the user is not yet in the group
            members = model.get_members()
            if user_id in members:
                context.message = u'The user is already here.'
                return

        # Set the role
        role = form['role']
        model.set_user_role(user_id, role)

        # Come back
        if context.has_form_value('add_and_return'):
            return

        goto='/users/%s/;%s' % (user.name, user.get_firstview())
        goto = get_reference(goto)
        return context.come_back(u'User added.', goto=goto)



###########################################################################
# Model
###########################################################################
class AccessControl(BaseAccessControl):

    def is_admin(self, user, object):
        if user is None:
            return False
        # WebSite admin?
        root = object.get_site_root()
        if root.has_user_role(user.name, 'admins'):
            return True
        # Global admin?
        root = object.get_root()
        return root.has_user_role(user.name, 'admins')


    def is_allowed_to_view(self, user, object):
        # Objects with workflow
        if isinstance(object, WorkflowAware):
            state = object.workflow_state
            # Anybody can see public objects
            if state == 'public':
                return True

            # Only those who can edit are allowed to see non-public objects
            return self.is_allowed_to_edit(user, object)

        # Everybody can see objects without workflow
        return True


    def is_allowed_to_edit(self, user, object):
        # By default only the admin can touch stuff
        return self.is_admin(user, object)


    # By default all other change operations (add, remove, copy, etc.)
    # are equivalent to "edit".
    def is_allowed_to_add(self, user, object):
        return self.is_allowed_to_edit(user, object)


    def is_allowed_to_remove(self, user, object):
        return self.is_allowed_to_edit(user, object)


    def is_allowed_to_copy(self, user, object):
        return self.is_allowed_to_edit(user, object)


    def is_allowed_to_move(self, user, object):
        return self.is_allowed_to_edit(user, object)


    def is_allowed_to_trans(self, user, object, name):
        return self.is_allowed_to_edit(user, object)



class RoleAware(AccessControl):
    """This base class implements access control based on the concept of
    roles.  Includes a user interface.
    """

    # To override
    __roles__ = [
        {'name': 'guests', 'title': u"Guest"},
        {'name': 'members', 'title': u"Member"},
        {'name': 'reviewers', 'title': u"Reviewer"},
        {'name': 'admins', 'title': u'Admin'},
    ]


    @classmethod
    def get_metadata_schema(cls):
        return {
            'guests': Tokens(default=()),
            'members': Tokens(default=()),
            'reviewers': Tokens(default=()),
            'admins': Tokens(default=()),
            'website_is_open': Boolean(default=False),
        }


    def get_links(self):
        return [ '/users/%s' % x for x in self.get_members() ]


    #########################################################################
    # Access Control
    #########################################################################
    def is_allowed_to_view(self, user, object):
        # Get the variables to resolve the formula
        # Intranet or Extranet
        is_open = self.get_property('website_is_open')
        # The role of the user
        if user is None:
            role = None
        elif self.is_admin(user, object):
            role = 'admins'
        else:
            role = self.get_user_role(user.name)
        # The state of the object
        if isinstance(object, WorkflowAware):
            state = object.workflow_state
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


    def is_allowed_to_edit(self, user, object):
        # Anonymous can touch nothing
        if user is None:
            return False

        # Admins are all powerfull
        if self.is_admin(user, object):
            return True

        # Reviewers too
        if self.has_user_role(user.name, 'reviewers'):
            return True

        # Members only can touch not-yet-published documents
        if self.has_user_role(user.name, 'members'):
            if isinstance(object, WorkflowAware):
                state = object.workflow_state
                # Anybody can see public objects
                if state != 'public':
                    return True

        return False


    def is_allowed_to_add(self, user, object):
        # Anonymous can touch nothing
        if user is None:
            return False

        # Admins are all powerfull
        if self.is_admin(user, object):
            return True

        # Reviewers too
        return self.has_user_role(user.name, 'reviewers', 'members')


    def is_allowed_to_trans(self, user, object, name):
        # Anonymous can touch nothing
        if user is None:
            return False

        # Admins are all powerfull
        if self.is_admin(user, object):
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
    def get_role_title(self, name):
        for role in self.__roles__:
            if role['name'] == name:
                return self.gettext(role['title'])
        return None


    def get_role_names(self):
        """Return the names of the roles available.
        """
        return [ r['name'] for r in self.__roles__ ]


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
        """Return True if the given user has any of the the given roles,
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
        namespace = [ {'name': x['name'], 'title': self.gettext(x['title'])}
                      for x in self.__roles__ ]

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
    permissions = PermissionsForm()
    edit_membership = MembershipForm()
    new_user = NewUserForm()
