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
from itools.core import merge_dicts
from itools.database import AndQuery, OrQuery, PhraseQuery, StartQuery
from itools.database import TextQuery
from itools.datatypes import Email, String, Unicode
from itools.gettext import MSG
from itools.web import ERROR, INFO

# Import from ikaaro
from access import is_admin
from autoform import AutoForm, TextWidget, PasswordWidget
from buttons import Button, RemoveButton
from config import Configuration
from messages import MSG_PASSWORD_MISMATCH
from resource_ import DBResource
from views import SearchForm



class BrowseUsers(SearchForm):

    access = 'is_admin'
    title = MSG(u'Browse Members')
    icon = 'userfolder.png'
    description = MSG(u'See the users.')

    schema = {'ids': String(multiple=True, mandatory=True)}

    def get_query_schema(self):
        return merge_dicts(SearchForm.get_query_schema(self),
                           sort_by=String(default='login_name'))


    search_schema = {
        'search_field': String,
        'search_term': Unicode}

    search_fields = []


    def get_items(self, resource, context):
        # Build the Query
        website_id = resource.get_site_root().get_abspath()
        search_query = AndQuery(
            PhraseQuery('format', 'user'),
            PhraseQuery('websites', str(website_id)))

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
        if sort_by in ('user_id', 'login_name'):
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
        website = resource.get_site_root()

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
            user = website.make_user(email, password)
            user_id = user.name
            if password is None:
                # Send confirmation email to activate the account
                user.send_confirmation(context, email)
            else:
                user.send_registration(context, email)
        else:
            user = users.get_resource(user_id)
            # Check the user is not yet in the group
            if user_id in website.get_members():
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
    class_version = '20110606'
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
