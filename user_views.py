# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007-2008 Sylvain Taverne <sylvain@itaapy.com>
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
from itools.datatypes import String
from itools.gettext import MSG
from itools.i18n import get_language_name
from itools.web import view, stl_view, INFO, ERROR, FormError
from itools.web import choice_field, email_field, password_field, text_field
from itools.xapian import PhraseQuery, AndQuery, OrQuery, StartQuery

# Import from ikaaro
from autoform import AutoForm
from buttons import RemoveButton
from folder import Folder_Table
import messages


class role_field(choice_field):

    required = True
    title = MSG(u'Role')


    @thingy_lazy_property
    def values(self):
        return self.view.workspace.roles



class User_ConfirmRegistration(stl_view):

    access = True
    template = '/ui/user/confirm_registration.xml'
    schema = {
        'key': String(mandatory=True),
        'newpass': String(mandatory=True),
        'newpass2': String(mandatory=True)}

    msg = MSG(u'To activate your account, please type a password.')

    def get_namespace(self, resource, context):
        # Check register key
        must_confirm = resource.get_property('user_must_confirm')
        username = context.get_form_value('username', default='')
        if must_confirm is None:
            return context.come_back(messages.MSG_REGISTERED,
                    goto='/;login?username=%s' % username)
        elif context.get_form_value('key') != must_confirm:
            return context.come_back(messages.MSG_BAD_KEY,
                    goto='/;login?username=%s' % username)

        # Ok
        return {
            'key': must_confirm,
            'username': resource.get_value('username'),
            'confirmation_msg': self.msg.gettext()}


    def action(self, resource, context, form):
        # Check register key
        must_confirm = resource.get_property('user_must_confirm')
        if form['key'] != must_confirm:
            context.message = messages.MSG_BAD_KEY
            return

        # Check passwords
        password = form['newpass']
        password2 = form['newpass2']
        if password != password2:
            context.message = messages.MSG_PASSWORD_MISMATCH
            return

        # Set user
        resource.set_password(password)
        resource.del_property('user_must_confirm')
        # Set cookie
        resource.set_auth_cookie(context, password)

        # Ok
        message = INFO(u'Operation successful! Welcome.')
        return context.come_back(message, goto='./')



class User_ChangePasswordForgotten(User_ConfirmRegistration):

    msg = MSG(u'Please choose a new password for your account')



class User_ResendConfirmation(view):

    access = 'is_admin'

    def GET(self, resource, context):
        # Already confirmed
        if not resource.has_property('user_must_confirm'):
            msg = MSG(u'User has already confirmed his registration!')
            return context.come_back(msg)

        # Resend confirmation
        resource.send_confirmation(context, resource.get_property('email'))
        # Ok
        msg = MSG(u'Confirmation sent!')
        return context.come_back(msg)



class User_Profile(stl_view):

    access = 'is_allowed_to_view'
    view_title = MSG(u'Profile')
    description = MSG(u"User's profile page.")
    icon = 'action_home.png'
    template = 'user/profile.xml'


    def user_must_confirm(self):
        return self.resource.has_property('user_must_confirm')


    def is_owner_or_admin(self):
        context = self.context
        resource = self.resource

        root = context.get_resource('/')
        user = context.user
        is_owner = user and user.path == resource.path
        return is_owner or root.is_admin(user, resource)


    def items(self):
        context = self.context
        resource = self.resource

        ac = resource.access_control

        # The icons menu
        items = []
        for name in ['edit_account', 'edit_preferences', 'edit_password',
                     'tasks']:
            # Get the view & check access rights
            view = resource.get_view(name)
            if view is None:
                continue
            if not ac.is_access_allowed(context, resource, view):
                continue
            # Append
            items.append({
                'url': ';%s' % name,
                'title': view.view_title,
                'description': getattr(view, 'description', None),
                'icon': resource.get_method_icon(view, size='48x48')})

        return items


@thingy_lazy_property
def value(self):
    return self.view.resource.get_value(self.name)



class User_EditAccount(AutoForm):

    access = 'is_allowed_to_edit'
    view_title = MSG(u'Edit Account')
    description = MSG(u'Edit your name and email address.')
    icon = 'card.png'

    firstname = text_field(value=value, title=MSG(u'First Name'))
    lastname = text_field(value=value, title=MSG(u'Last Name'))
    email = email_field(value=value, title=MSG(u"E-mail Address"))
    password = password_field(required=True)
    password.title = MSG(u"To confirm these changes, you must type your "
                         u"password")


    def get_field_names(self):
        if self.resource is self.context.user:
            return ['firstname', 'lastname', 'email', 'password']
        return ['firstname', 'lastname', 'email']


    def cook(self, method):
        super(User_EditAccount, self).cook(method)
        if method == 'get':
            return

        resource = self.resource
        context = self.context

        # Check password to confirm changes
        if resource is context.user:
            password = self.password.value
            if not resource.authenticate(password):
                self.password.error = MSG(u"Wrong password")
                raise FormError

        # If the user changes his email, check there is not already other
        # user with the same email in the database.
        email = self.email.value
        if email != resource.get_value('email'):
            shared_user = context.get_shared_user_by_email(email)
            if shared_user:
                msg = u"There's another user with the {email} email address"
                self.email.error = MSG(msg).gettext(email=email)
                raise FormError


    def action(self):
        # Save changes
        resource = self.resource
        resource.set_property('firstname', self.firstname.value)
        resource.set_property('lastname', self.lastname.value)
        resource.set_property('email', self.email.value)
        # Ok
        context = self.context
        context.message = INFO(u'Account changed.')
        context.redirect()



class User_EditPreferences(stl_view):

    access = 'is_allowed_to_edit'
    view_title = MSG(u'Edit Preferences')
    description = MSG(u'Set your preferred language.')
    icon = 'preferences.png'
    template = 'user/edit_preferences.xml'

    user_language = choice_field()


    def languages(self):
        user_language = self.resource.get_value('user_language')
        return [
            {'code': code,
             'name': get_language_name(code),
             'is_selected': code == user_language}
            for code in self.context.software_languages ]


    def action(self):
        value = self.user_language.value
        if value == '':
            self.resource.del_property('user_language')
        else:
            self.resource.set_property('user_language', value)
        # Ok
        context = self.context
        context.message = INFO(u'Application preferences changed.')
        context.redirect()



class User_EditPassword(stl_view):

    access = 'is_allowed_to_edit'
    view_title = MSG(u'Edit Password')
    description = MSG(u'Change your password.')
    icon = 'lock.png'
    template = 'user/edit_password.xml'
    schema = {
        'newpass': String(mandatory=True),
        'newpass2': String(mandatory=True),
        'password': String}


    def get_namespace(self, resource, context):
        user = context.user
        return {
            'must_confirm': (resource.path == user.path)}


    def action(self, resource, context, form):
        newpass = form['newpass'].strip()
        newpass2 = form['newpass2']

        # Check password to confirm changes
        is_same_user = (resource.get_name() == context.user.get_name())
        if is_same_user:
            password = form['password']
            if not resource.authenticate(password):
                context.message = ERROR(
                    u"You mistyped your actual password, your account is"
                    u" not changed.")
                return

        # Check the new password matches
        if newpass != newpass2:
            context.message = ERROR(
                    u"Passwords mismatch, please try again.")
            return

        # Clear confirmation key
        if resource.has_property('user_must_confirm'):
            resource.del_property('user_must_confirm')

        # Set password
        resource.set_password(newpass)

        # Update the cookie if we updated our own password
        if is_same_user:
            resource.set_auth_cookie(context, newpass)

        # Ok
        context.message = INFO(u'Password changed.')



class User_EditRole(AutoForm):

    access = 'is_admin'
    view_title = MSG(u'Edit role')

    role = role_field(mode='radio')


    @thingy_lazy_property
    def workspace(self):
        return self.resource.get_parent().get_parent()


    @thingy_lazy_property
    def role__value(self):
        return self.view.resource.get_value('role')



class User_Tasks(stl_view):

    access = 'is_allowed_to_edit'
    view_title = MSG(u'Tasks')
    description = MSG(u'See your pending tasks.')
    icon = 'tasks.png'
    template = 'user/tasks.xml'


    def get_namespace(self, resource, context):
        user = context.user

        # Build the query
        site_root = resource.get_site_root()
        q1 = PhraseQuery('workflow_state', 'pending')
        q2 = OrQuery(StartQuery('abspath', str(site_root.get_abspath())),
                     StartQuery('abspath',
                                     str(resource.get_canonical_path())))
        query = AndQuery(q1, q2)

        # Build the list of documents
        documents = []
        for document in context.search(query).get_documents():
            # Check security
            ac = document.access_control
            if not ac.is_allowed_to_view(user, document):
                continue
            # Append
            documents.append(
                {'url': '%s/' % resource.get_pathto(document),
                 'title': document.get_title()})

        return {'documents': documents}



class UserFolder_Table(Folder_Table):

    access = 'is_admin'
    view_title = MSG(u'Users')

    search = Folder_Table.search()
    search.search_fields = freeze(
        ['username', 'lastname', 'firstname', 'email_domain'])

    form = Folder_Table.form()
    form.content = form.content()
    form.content.header = [
        ('checkbox', None, False),
        ('user_id', MSG(u'User ID'), True),
        ('login_name', MSG(u'Login'), True),
        ('firstname', MSG(u'First Name'), True),
        ('lastname', MSG(u'Last Name'), True),
        ('role', MSG(u'Role'), True),
        ('account_state', MSG(u'State'), True)]

    form.actions = [RemoveButton]


    def get_item_value(self, item, column):
        if column == 'checkbox':
            return str(item.path), False
        elif column == 'user_id':
            name = item.get_name()
            return name, name
        elif column == 'login_name':
            return item.get_value('username')
        elif column == 'firstname':
            return item.get_value('firstname')
        elif column == 'lastname':
            return item.get_value('lastname')
        elif column == 'role':
            name = item.get_name()
            role = item.get_role_title()
            return role, '%s/;edit_role' % name
        elif column == 'account_state':
            if item.get_value('user_must_confirm'):
                href = '/users/%s/;resend_confirmation' % item.get_name()
                return MSG(u'Resend Confirmation'), href
            return MSG(u'Active'), None


    def cook(self, method):
        super(UserFolder_Table, self).cook(method)

        if self.context.user.path in self.ids.value:
            raise FormError, ERROR(u'You cannot remove yourself.')


class UserFolder_AddUser(stl_view):

    access = 'is_admin'
    view_title = MSG(u'Add user')
    view_description = MSG(u'Grant access to a new user.')
    icon = 'card.png'
    template = 'access/add_user.xml'

    email = email_field(required=True)
    email.title = MSG(u'Email')
    role = role_field()
    newpass = password_field(title=MSG(u'Password'))
    newpass2 =  password_field(title=MSG(u'Repeat Password'))


    @thingy_lazy_property
    def workspace(self):
        return self.resource.get_parent()


    def is_admin(self):
        return self.workspace.is_admin(self.context.user, self.resource)


    def cook(self, method):
        super(UserFolder_AddUser, self).cook(method)
        if method == 'get':
            return

        # Check the user is not yet in the group
        email = self.email.value.strip()
        results = self.context.search(format='user', email=email)
        if len(results):
            self.email.error = ERROR(u'The user is already here.')
            raise FormError

        # Check passwords match
        if self.newpass.value != self.newpass2.value:
            self.newpass2.error = messages.MSG_PASSWORD_MISMATCH
            raise FormError


    def action(self):
        context = self.context

        # (1) Get the master user, make it if needed
        email = self.email.value.strip()
        shared_user = context.get_shared_user_by_email(email)
        if not shared_user:
            user = context.make_shared_user()
            user.set_property('email', email)
            # Password
            password = self.newpass.value
            if password:
                user.set_password(password)
            else:
                user.send_confirmation(context, email)

        # (2) Add user to this website
        username = user.get_name()
        users = context.get_resource('/users')
        user = users.get_resource(username, soft=True)
        if user is None:
            cls = get_resource_class('user')
            user = users.make_resource(username, cls)

        # (3) Set role
        role = self.role.value
        user.set_property('role', role)

        # Ok
        context.message = INFO(u'User added.')
        context.created('/users/%s' % username)

