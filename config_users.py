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
from itools.datatypes import Email, String
from itools.gettext import MSG
from itools.web import ERROR, INFO

# Import from ikaaro
from autoform import AutoForm, TextWidget, PasswordWidget
from buttons import Button, BrowseButton
from config import Configuration
from messages import MSG_CHANGES_SAVED, MSG_PASSWORD_MISMATCH
from resource_ import DBResource
from user_views import BrowseUsers



class AddUser(AutoForm):

    access = 'is_admin'
    title = MSG(u'Add New Member')
    icon = 'card.png'
    description = MSG(u'Grant access to a new user.')

    schema = {
        'email': Email(mandatory=True),
        'newpass': String,
        'newpass2': String}

    widgets = [
        TextWidget('email', title=MSG(u'Email')),
        # Admin can set user password
        PasswordWidget('newpass', title=MSG(u'Password'),
                       tip=MSG(u'If no password is given an email will be '
                               u' sent to the user, asking him to choose '
                               u' his password.')),
        PasswordWidget('newpass2', title=MSG(u'Repeat Password'))]

    actions = [
        Button(access='is_admin', css='button-ok', name='add_and_view',
               title=MSG(u'Add and view')),
        Button(access='is_admin', css='button-ok', name='add_and_return',
               title=MSG(u'Add and return'))]


    def _add(self, resource, context, form):
        # Check whether the user already exists
        email = form['email'].strip()
        results = context.search(email=email)
        if len(results):
            context.message = ERROR(u'The user is already here.')
            return None

        # Create user
        password = form['newpass']
        password2 = form['newpass2']
        # Check the password is right
        if password != password2:
            context.message = MSG_PASSWORD_MISMATCH
            return None
        if not password:
            # Admin can set no password
            # so the user must activate its account
            password = None
        # Add the user
        user = context.root.make_user(password=password)
        user.set_property('email', email)
        if password is None:
            # Send confirmation email to activate the account
            user.send_confirmation(context, email)
        else:
            user.send_registration(context, email)

        return user.name


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



class ConfigUsers_Browse(BrowseUsers):

    table_actions = [
        BrowseButton(access='is_admin', name='switch_state',
                     title=MSG(u'Switch state'))]


    def action_switch_state(self, resource, context, form):
        # Verify if after this operation, all is ok
        usernames = form['ids']
        if context.user.name in usernames:
            context.message = ERROR(u'You cannot change your state yourself.')
            return

        database = resource.database
        for username in usernames:
            user = database.get_resource('/users/%s' % username)
            user_state = user.get_value('user_state')
            if user_state == 'active':
                user.set_value('user_state', 'inactive')
            elif user_state == 'inactive':
                user.set_value('user_state', 'active')
            else: # pending
                continue

        # Ok
        context.message = MSG_CHANGES_SAVED



class ConfigUsers(DBResource):

    class_id = 'config-users'
    class_title = MSG(u'Users')
    class_description = MSG(u'Manage users.')
    class_icon48 = 'icons/48x48/userfolder.png'

    # Views
    class_views = ['browse_users', 'add_user']
    browse_users = ConfigUsers_Browse()
    add_user = AddUser()

    # Configuration
    config_name = 'users'
    config_group = 'access'


# Register
Configuration.register_plugin(ConfigUsers)
