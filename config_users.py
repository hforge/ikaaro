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
from buttons import Button
from config import Configuration
from messages import MSG_PASSWORD_MISMATCH
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
            user = root.make_user(password=password)
            user.set_property('email', email)
            user_id = user.name
            if password is None:
                # Send confirmation email to activate the account
                user.send_confirmation(context, email)
            else:
                user.send_registration(context, email)
        else:
            user = users.get_resource(user_id)
            # Check the user is not yet in the group
            if user_id in root.get_members():
                context.message = ERROR(u'The user is already here.')
                return None
            user.send_registration(context, email)

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


class ConfigUsers(DBResource):

    class_id = 'config-users'
    class_title = MSG(u'Users')
    class_description = MSG(u'Manage users.')
    class_icon48 = 'icons/48x48/userfolder.png'

    # Views
    class_views = ['browse_users', 'add_user']
    browse_users = BrowseUsers()
    add_user = AddUser()

    # Configuration
    config_name = 'users'
    config_group = 'access'


# Register
Configuration.register_plugin(ConfigUsers)
