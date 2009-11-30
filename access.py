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
from itools.datatypes import Tokens, String
from itools.gettext import MSG
from itools.web import AccessControl as BaseAccessControl
from itools.web import ERROR, stl_view
from itools.web import multiple_choice_field
from itools.web import readonly_field

# Import from ikaaro
from autoform import AutoForm
from views import Container_Search, Container_Sort, Container_Batch
from views import Container_Table
from workflow import WorkflowAware


###########################################################################
# Utility
###########################################################################
def is_admin(user):
    return user and user.get_value('role') == 'admin'


###########################################################################
# Views
###########################################################################
class RoleAware_BrowseUsers(stl_view):

    access = 'is_admin'
    view_title = MSG(u'Browse Members')
    view_description = MSG(u'See the users and their roles.')
    icon = 'userfolder.png'

    search = Container_Search()

    sort = Container_Sort()
    sort.sort_by = sort.sort_by(value='login_name')

    batch = Container_Batch()

    table = Container_Table()

    ids = multiple_choice_field(required=True)


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



class user_field(readonly_field):

    @thingy_lazy_property
    def displayed(self):
        return self.view.context.get_user_title(self.value)



class RoleAware_EditMembership(AutoForm):

    access = 'is_admin'
    view_title = MSG(u'Change role')

    id = user_field(required=True, title=MSG(u'User'))


    # the 'id' field must be cooked before the 'role' field
    field_names = ['id', 'role']


    def action(self):
        context = self.context

        user_id = self.id.value
        role = self.role.value

        # Verify if after this operation, all is ok
        user = context.user
        if str(user.get_name()) == user_id and role != 'admins':
            if not is_admin(user):
                context.message = ERROR(u'You cannot degrade your own role.')
                return

        # Make the operation
        self.resource.set_user_role(user_id, role)

        # Ok
        context.message = u"Role updated."
        context.redirect()



###########################################################################
# Model
###########################################################################
class AccessControl(BaseAccessControl):

    def is_admin(self, user, resource):
        return is_admin(user)


    def is_allowed_to_view(self, user, resource):
        # Resources with workflow
        if issubclass(resource, WorkflowAware):
            state = resource.get_value('workflow_state')
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
        if not issubclass(resource, WorkflowAware):
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
        # Metadata (roles)
        'guests': Tokens(source='metadata', title=MSG(u"Guest")),
        'members': Tokens(source='metadata', title=MSG(u"Member")),
        'reviewers': Tokens(source='metadata', title=MSG(u"Reviewer")),
        'admins': Tokens(source='metadata', title=MSG(u'Admin')),
        # Other
        'users': String(multiple=True, indexed=True)})


    def get_links(self):
        return [ '/users/%s' % x for x in self.get_users() ]


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
        if issubclass(resource, WorkflowAware):
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
            if issubclass(resource, WorkflowAware):
                state = resource.get_value('workflow_state')
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
        if not issubclass(resource, WorkflowAware):
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
    # UI / Views
    #######################################################################
    browse_users = RoleAware_BrowseUsers
    edit_membership = RoleAware_EditMembership

