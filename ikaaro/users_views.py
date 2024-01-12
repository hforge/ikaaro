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
from itools.core import freeze, merge_dicts, proto_lazy_property
from itools.database import PhraseQuery, StartQuery, TextQuery
from itools.database import AndQuery, OrQuery
from itools.datatypes import String, Unicode
from itools.gettext import MSG
from itools.i18n import get_language_name
from itools.web import BaseView, FormError, STLView, INFO, ERROR

# Import from pytz
from pytz import common_timezones

# Import from ikaaro
from .autoadd import AutoAdd
from .autoedit import AutoEdit
from .autoform import AutoForm
from .buttons import Button, BrowseButton
from .datatypes import ChoosePassword_Datatype
from .emails import send_email
from .fields import Password_Field, ChoosePassword_Field
from . import messages
from .views import BrowseForm
from .widgets import HiddenWidget, ReadOnlyWidget, TextWidget
from .widgets import PasswordWidget, ChoosePassword_Widget


class User_ConfirmRegistration(AutoForm):

    access = True
    title = MSG('Choose your password')
    description = MSG('To activate your account, please type a password.')

    schema = freeze({
        'key': String(mandatory=True),
        'username': String,
        'newpass': ChoosePassword_Datatype(mandatory=True),
        'newpass2': String(mandatory=True)})
    widgets = freeze([
        HiddenWidget('key'),
        ReadOnlyWidget('username', title=MSG('Username')),
        ChoosePassword_Widget('newpass', userid='username'),
        PasswordWidget('newpass2', title=MSG('Repeat password'))])


    def get_value(self, resource, context, name, datatype):
        if name == 'key':
            return resource.get_property('user_state').get_parameter('key')
        if name == 'username':
            return resource.get_login_name()

        proxy = super(User_ConfirmRegistration, self)
        return proxy.get_value(resource, context, name, datatype)


    def get_namespace(self, resource, context):
        # Check register key
        username = context.get_form_value('username', default='')

        key = resource.get_property('user_state').get_parameter('key')
        if key is None:
            goto = f'/;login?username={username}'
            return context.come_back(messages.MSG_REGISTERED, goto=goto)
        elif context.get_form_value('key') != key:
            goto =f'/;login?username={username}'
            return context.come_back(messages.MSG_BAD_KEY, goto=goto)

        proxy = super(User_ConfirmRegistration, self)
        return proxy.get_namespace(resource, context)


    def _get_form(self, resource, context):
        proxy = super(User_ConfirmRegistration, self)
        form = proxy._get_form(resource, context)
        if form['username'] == form['newpass']:
            raise FormError(messages.MSG_PASSWORD_EQUAL_TO_USERNAME)
        return form


    def action(self, resource, context, form):
        # Check register key
        key = resource.get_property('user_state').get_parameter('key')
        if not key:
            context.message = MSG('User is not pending')
            return

        if form['key'] != key:
            context.message = messages.MSG_BAD_KEY
            return

        # Check passwords
        password = form['newpass']
        password2 = form['newpass2']
        if password != password2:
            context.message = messages.MSG_PASSWORD_MISMATCH
            return

        # Set user
        resource.set_value('password', password)
        resource.del_property('user_state')
        # Set cookie
        resource._login(password, context)

        # Send email
        to_addr = resource.get_value('email')
        send_email('register-send-confirmation', context, to_addr,
                   user=resource)

        # Ok
        message = INFO('Operation successful! Welcome.')
        return context.come_back(message, goto='./')



class User_ChangePasswordForgotten(User_ConfirmRegistration):

    description = MSG('Please choose a new password for your account')



class User_ResendConfirmation(BaseView):

    access = 'is_admin'

    def GET(self, resource, context):
        # Already confirmed
        user_state = resource.get_value('user_state')
        if user_state != 'pending':
            msg = MSG('User has already confirmed his registration!')
            return context.come_back(msg)

        # Resend confirmation
        resource.update_pending_key()
        email = resource.get_value('email')
        send_email('user-ask-for-confirmation', context, email, user=resource)
        # Ok
        msg = MSG('Confirmation sent!')
        return context.come_back(msg)



class User_Profile(STLView):

    access = 'is_allowed_to_view'
    title = MSG('Profile')
    description = MSG("User's profile page.")
    icon = 'action_home.png'
    template = '/ui/ikaaro/user/profile.xml'

    items = ['edit_account', 'edit_preferences', 'edit_password']


    def get_items(self, resource, context):
        items = []
        for name in self.items:
            # Get the view & check access rights
            view = resource.get_view(name)
            if view and context.is_access_allowed(resource, view):
                items.append({
                    'url': f';{name}',
                    'title': view.title,
                    'description': getattr(view, 'description', None),
                    'icon': resource.get_method_icon(view, size='48x48')})
        return items


    def get_namespace(self, resource, context):
        avatar = resource.get_value('avatar')
        state = resource.get_value('user_state')
        return {
            'firstname': resource.get_value('firstname'),
            'lastname': resource.get_value('lastname'),
            'avatar': avatar is not None,
            'items': self.get_items(resource, context),
            'user_is_active': (state == 'active')}



class User_EditAccount(AutoEdit):

    access = 'is_allowed_to_edit'
    title = MSG('Edit Account')
    description = MSG('Edit your name and email address.')
    icon = 'card.png'


    # TODO The email address must be verified when changed. We should allow
    # users to have several email addresses.
    fields = ['firstname', 'lastname', 'avatar', 'email']


    def set_value(self, resource, context, name, form):
        field = resource.get_field(name)
        if getattr(field, 'unique', False):
            old_value = resource.get_value(name)
            new_value = form[name]
            if old_value != new_value:
                query = PhraseQuery(name, new_value)
                results = context.database.search(query)
                if len(results):
                    error = (
                        'There is another user with the "{value}" {name},'
                        ' please choose another one.')
                    context.message = ERROR(error, name=name, value=new_value)
                    return True

        proxy = super(User_EditAccount, self)
        return proxy.set_value(resource, context, name, form)



class User_EditPreferences(STLView):

    access = 'is_allowed_to_edit'
    title = MSG('Edit Preferences')
    description = MSG('Set your preferred language and timezone.')
    icon = 'preferences.png'
    template = '/ui/ikaaro/user/edit_preferences.xml'
    schema = {
        'user_language': String,
        'user_timezone': String}


    def get_namespace(self, resource, context):
        root = context.root

        # Languages
        user_language = resource.get_value('user_language')
        languages = [
            {'code': code,
             'name': get_language_name(code),
             'is_selected': code == user_language}
            for code in root.get_available_languages() ]

        # Timezone
        user_timezone = resource.get_value('user_timezone')
        timezones = [
            {'name': name,
             'is_selected': name == user_timezone}
            for name in common_timezones ]

        return {'languages': languages,
                'timezones': timezones}


    def action(self, resource, context, form):
        value = form['user_language']
        if value == '':
            resource.del_property('user_language')
        else:
            resource.set_property('user_language', value)
        value = form['user_timezone']
        if value == '':
            resource.del_property('user_timezone')
        else:
            resource.set_property('user_timezone', value)
        # Ok
        context.message = messages.MSG_CHANGES_SAVED



class User_EditPassword(AutoForm):

    access = 'is_allowed_to_edit'
    title = MSG('Edit Password')
    description = MSG('Change your password.')
    icon = 'lock.png'

    schema = freeze({
        'username': String,
        'newpass': ChoosePassword_Datatype(mandatory=True),
        'newpass2': String(mandatory=True)})
    widgets = [
        HiddenWidget('username'),
        ChoosePassword_Widget('newpass', userid='username',
                              title=MSG('New password')),
        PasswordWidget('newpass2', title=MSG('Confirm'))]


    def get_schema(self, resource, context):
        if resource.name != context.user.name:
            return self.schema
        return merge_dicts(self.schema, password=String(mandatory=True))


    def get_widgets(self, resource, context):
        if resource.name != context.user.name:
            return self.widgets
        title = MSG('Type your current password')
        return self.widgets + [PasswordWidget('password', title=title)]


    def get_value(self, resource, context, name, datatype):
        if name == 'username':
            return resource.get_login_name()

        proxy = super(User_EditPassword, self)
        return proxy.get_value(resource, context, name, datatype)


    def _get_form(self, resource, context):
        form = super(User_EditPassword, self)._get_form(resource, context)

        # Strip password
        newpass = form['newpass'].strip()
        form['newpass'] = newpass

        # Check username is different from password
        if form['username'] == form['newpass']:
            raise FormError(messages.MSG_PASSWORD_EQUAL_TO_USERNAME)

        # Check the new password matches
        if newpass != form['newpass2']:
            raise FormError(ERROR("Passwords mismatch, please try again."))

        # Check old password
        if resource.name == context.user.name:
            password = form['password']
            if not resource.authenticate(password):
                message = ERROR(
                    "You mistyped your actual password, your account is"
                    " not changed.")
                raise FormError(message)

        # Ok
        return form


    def action(self, resource, context, form):
        # Clear confirmation key and set password
        resource.set_value('user_state', None)
        resource.set_value('password', form['newpass'].strip())

        # Relogin
        if resource.name == context.user.name:
            context.login(resource)

        # Ok
        context.message = messages.MSG_CHANGES_SAVED



###########################################################################
# Container
###########################################################################
class BrowseUsers(BrowseForm):

    access = 'is_admin'
    title = MSG('Browse Members')
    icon = 'userfolder.png'
    description = MSG('See the users.')

    schema = {'ids': String(multiple=True, mandatory=True)}

    def get_query_schema(self):
        schema = super(BrowseUsers, self).get_query_schema()
        return merge_dicts(schema, sort_by=String(default='email'))


    search_schema = {'search_term': Unicode}
    search_widgets = [TextWidget('search_term', title=MSG('Search'))]

    def get_items(self, resource, context):
        # Build the Query
        search_query = PhraseQuery('format', 'user')
        search_term = context.query['search_term'].strip()
        if search_term:
            search_query = AndQuery(search_query)
            or_query = OrQuery(
                TextQuery('lastname', search_term),
                TextQuery('firstname', search_term),
                StartQuery('email', search_term),
                StartQuery('email_domain', search_term))
            search_query.append(or_query)

        # Ok
        return context.search(search_query)


    def sort_and_batch(self, resource, context, results):
        start = context.query['batch_start']
        size = context.query['batch_size']
        sort_by = context.query['sort_by']
        reverse = context.query['reverse']

        # Slow
        if sort_by == 'account_state':
            f = lambda x: self.get_item_value(resource, context, x,
                                              sort_by)[0].gettext()
            items = results.get_resources()
            items = list(items)
            items = sorted(items, key=lambda x: f(x), reverse=reverse)
            items = items[start:start+size]
            database = resource.database
            return [ database.get_resource(x.abspath) for x in items ]

        # Fast
        items = results.get_resources(sort_by, reverse, start, size)
        return list(items)


    table_columns = [
        ('checkbox', None),
        ('name', MSG('User ID')),
        ('email', MSG('Login')),
        ('firstname', MSG('First Name')),
        ('lastname', MSG('Last Name')),
        ('account_state', MSG('State'))]


    def get_item_value(self, resource, context, item, column):
        if column == 'checkbox':
            return item.name, False
        elif column == 'name':
            return item.name, str(item.abspath)
        elif column == 'account_state':
            if item.get_value('user_state') == 'pending':
                href = f'/users/{item.name}/;resend_confirmation'
                return MSG('Resend Confirmation'), href

            return item.get_value_title('user_state'), None

        return item.get_value_title(column)



class Users_Browse(BrowseUsers):

    table_actions = [
        BrowseButton(access='is_admin', name='switch_state',
                     title=MSG('Switch state'))]


    def action_switch_state(self, resource, context, form):
        # Verify if after this operation, all is ok
        usernames = form['ids']
        if context.user.name in usernames:
            context.message = ERROR('You cannot change your state yourself.')
            return

        database = resource.database
        for username in usernames:
            user = database.get_resource(f'/users/{username}')
            email = user.get_value('email')
            user_state = user.get_value('user_state')
            if user_state == 'active':
                user.set_value('user_state', 'inactive')
                send_email('switch-state-deactivate', context, email)
            elif user_state == 'inactive':
                user.set_value('user_state', 'active')
                send_email('switch-state-activate', context, email)
            else: # pending
                continue

        # Ok
        context.message = messages.MSG_CHANGES_SAVED



class Users_AddUser(AutoAdd):

    access = 'is_admin'
    title = MSG('Add New Member')
    icon = 'card.png'
    description = MSG('Grant access to a new user.')

    fields = ['email', 'password', 'password2', 'groups']

    password = ChoosePassword_Field(title=MSG('Password'), userid='email')
    password.tip = MSG('If no password is given an email will be sent to the'
                       ' user, asking him to choose his password.')
    password2 = Password_Field(title=MSG('Repeat password'), datatype=String)


    @proto_lazy_property
    def _resource_class(self):
        return self.context.database.get_resource_class('user')


    def _get_form(self, resource, context):
        form = super(Users_AddUser, self)._get_form(resource, context)

        # Check the password is not equal to the username
        password = form['password'].strip()
        if form['email'] == password:
            raise FormError(messages.MSG_PASSWORD_EQUAL_TO_USERNAME)

        # Check whether the user already exists
        email = form['email'].strip()
        results = context.search(email=email)
        if len(results):
            raise FormError(ERROR('The user is already here.'))

        # Check the password is right
        if password != form['password2']:
            raise FormError(messages.MSG_PASSWORD_MISMATCH)
        if password == '':
            form['password'] = None

        return form


    actions = [
        Button(access='is_admin', css='btn btn-primary',
               title=MSG('Add and view')),
        Button(access='is_admin', css='btn btn-primary', name='add_and_return',
               title=MSG('Add and return'))]


    def get_container(self, resource, context, form):
        return resource.get_resource('/users')


    automatic_resource_name = True


    def make_new_resource(self, resource, context, form):
        proxy = super(Users_AddUser, self)
        child = proxy.make_new_resource(resource, context, form)

        # Send email to the new user
        if child:
            if form['password']:
                email_id = 'add-user-send-notification'
            else:
                child.update_pending_key()
                email_id = 'user-ask-for-confirmation'

            send_email(email_id, context, form['email'], user=child)

        # Ok
        return child


    def action_add_and_return(self, resource, context, form):
        child = self.make_new_resource(resource, context, form)
        if child is None:
            return

        context.message = INFO('User added.')
