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
from itools.core import merge_dicts
from itools.database import AndQuery, OrQuery, PhraseQuery, StartQuery
from itools.database import TextQuery
from itools.datatypes import Email, Enumerate, String, Unicode
from itools.gettext import MSG
from itools.web import AccessControl as BaseAccessControl, ERROR, INFO

# Import from ikaaro
from autoform import AutoForm, HiddenWidget, TextWidget, PasswordWidget
from autoform import RadioWidget, SelectWidget
from buttons import Button
from buttons import RemoveButton
from views import SearchForm
from workflow import WorkflowAware
import messages



###########################################################################
# Utility
###########################################################################
def is_admin(user, resource):
    if user is None or resource is None:
        return False
    # WebSite admin?
    root = resource.get_site_root()
    if root.has_user_role(user, 'admins'):
        return True
    # Global admin?
    root = resource.get_root()
    return root.has_user_role(user, 'admins')



class Roles_Datatype(Enumerate):

    resource = None

    def get_options(self):
        site_root = self.resource.get_site_root()
        options = [
            {'name': x['name'], 'value': x['title']}
            for x in site_root.get_roles_namespace() ]

        # Root admins (TODO special case, to remove)
        if site_root.parent is not None:
            options.append(
                {'name': 'root-admins', 'value': MSG(u'Admin (root)')})

        return options


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

    search_fields = []


    def get_items(self, resource, context):
        resource = resource.get_access_control()

        # Build the Query
        groups = resource.get_groups()
        search_query = AndQuery(
            PhraseQuery('format', 'user'),
            OrQuery(* [ PhraseQuery('groups', x) for x in groups ]))

        search_term = context.query['search_term'].strip()
        if search_term:
            or_query = OrQuery(
                TextQuery('lastname', search_term),
                TextQuery('firstname', search_term),
                StartQuery('username', search_term),
                StartQuery('email_domain', search_term))
            search_query.append(or_query)

        # Ok
        results = context.root.search(search_query)
        return results.get_documents()


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
            ac = resource.get_access_control()
            user = context.root.get_resource(item.abspath)
            user_groups = set(user.get_property('groups'))
            groups = u', '.join([
                x.get_title() for x in ac.get_resources('config/groups')
                if x.get_abspath() in user_groups ])
            href = '/%s/;edit_membership?id=%s' % (
                    context.site_root.get_pathto(resource), item.name)
            return groups, href
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



class RoleAware_EditMembership(AutoForm):

    access = 'is_admin'

    widgets = [HiddenWidget('id'),
               RadioWidget('role', title=MSG(u'Roles available'),
                           has_empty_option=False)]

    actions = [Button(access='is_admin', css='button-rename',
                      title=MSG(u'Update'))]


    def get_title(self, context):
        user_id = context.get_form_value('id')
        user = context.resource.get_resource('/users/%s' % user_id)
        return MSG(u'Change Role of {name}').gettext(name=user.get_title())


    def get_schema(self, resource, context):
        return {'id': String(mandatory=True),
                'role': Roles_Datatype(resource=resource, mandatory=True)}


    def get_value(self, resource, context, name, datatype):
        user_id = context.get_form_value('id')
        if name == 'id':
            return user_id
        elif name == 'role':
            return resource.get_user_role(user_id)


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



class RoleAware_AddUser(AutoForm):

    access = 'is_admin'
    title = MSG(u'Add New Member')
    icon = 'card.png'
    description = MSG(u'Grant access to a new user.')

    actions = [
        Button(access='is_admin', css='button-ok', name='add_and_view',
               title=MSG(u'Add and view')),
        Button(access='is_admin', css='button-ok', name='add_and_return',
               title=MSG(u'Add and return'))]


    def get_schema(self, resource, context):
        resource = resource.get_access_control()
        schema = {'email': Email(mandatory=True)}

        # Build role datatype
        options = [ {'name': x['name'], 'value': x['title']}
                    for x in resource.get_roles_namespace() ]
        schema['role'] = Enumerate(options=options, mandatory=True)

        # Admin can set user password
        if resource.is_admin(context.user, resource):
            schema['newpass'] = String
            schema['newpass2'] = String

        return schema


    def get_widgets(self, resource, context):
        resource = resource.get_access_control()
        widgets = [TextWidget('email', title=MSG(u'Email'))]

        # Admin can set user password
        if resource.is_admin(context.user, resource):
            tip = MSG(
                u'If no password is given an email will be sent to the user,'
                u' asking him to choose his password.')
            widgets.append(
                PasswordWidget('newpass', title=MSG(u'Password'), tip=tip))
            widgets.append(
                PasswordWidget('newpass2', title=MSG(u'Repeat Password')))

        # Role widget
        title = MSG(u'Choose the role for the new member')
        widgets.append(
            SelectWidget('role', has_empty_option=False, title=title))

        return widgets


    def _add(self, resource, context, form):
        root = context.root
        user = context.user
        users = root.get_resource('users')

        # Check whether the user already exists
        email = form['email'].strip()
        results = root.search(email=email)
        if len(results):
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
                    return None
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
                user.send_registration(context, email)
        else:
            user = users.get_resource(user_id)
            # Check the user is not yet in the group
            if user_id in resource.get_members():
                context.message = ERROR(u'The user is already here.')
                return None
            user.send_registration(context, email)

        # Set the role
        role = form['role']
        resource.set_user_role(user_id, role)
        return user_id


    def action_add_and_return(self, resource, context, form):
        user_id = self._add(resource, context, form)
        if user_id is not None:
            context.message = INFO(u'User added.')


    def action_add_and_view(self, resource, context, form):
        user_id = self._add(resource, context, form)
        if user_id is not None:
            goto = '/users/%s/' % user_id
            message = INFO(u'User added.')
            return context.come_back(message, goto=goto)


###########################################################################
# Model
###########################################################################
class AccessControl(BaseAccessControl):

    def is_admin(self, user, resource):
        return is_admin(user, resource)


    def is_owner_or_admin(self, user, resource):
        if user is None:
            return False
        if self.is_admin(user, resource):
            return True
        owner = resource.get_owner()
        return owner == user.name


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
    def is_allowed_to_put(self, user, resource):
        return self.is_allowed_to_edit(user, resource)


    def is_allowed_to_add(self, user, resource, class_id=None):
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
