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
from itools.core import freeze, merge_dicts
from itools.datatypes import Email, String, Unicode, DateTime
from itools.gettext import MSG
from itools.i18n import get_language_name
from itools.web import BaseView, STLView, STLForm, INFO, ERROR
from itools.database import PhraseQuery, AndQuery, OrQuery, StartQuery

# Import from pytz
from pytz import common_timezones

# Import from ikaaro
from autoform import AutoForm, timestamp_widget
from autoform import HiddenWidget, PasswordWidget, ReadOnlyWidget, TextWidget
from folder import Folder_BrowseContent
import messages
from resource_views import DBResource_Edit


class User_ConfirmRegistration(AutoForm):

    access = True
    title = MSG(u'Choose your password')
    description = MSG(u'To activate your account, please type a password.')

    schema = freeze({
        'key': String(mandatory=True),
        'username': String,
        'newpass': String(mandatory=True),
        'newpass2': String(mandatory=True)})
    widgets = freeze([
        HiddenWidget('key'),
        ReadOnlyWidget('username', title=MSG(u'Username')),
        PasswordWidget('newpass', title=MSG(u'Password')),
        PasswordWidget('newpass2', title=MSG(u'Repeat password'))])


    def get_value(self, resource, context, name, datatype):
        if name == 'key':
            return resource.get_property('user_must_confirm')
        if name == 'username':
            return resource.get_login_name()

        return AutoForm.get_value(self, resource, context, name, datatype)


    def get_namespace(self, resource, context):
        # Check register key
        must_confirm = resource.get_property('user_must_confirm')
        username = context.get_form_value('username', default='')
        if must_confirm is None:
            goto = '/;login?username=%s' % username
            return context.come_back(messages.MSG_REGISTERED, goto=goto)
        elif context.get_form_value('key') != must_confirm:
            goto ='/;login?username=%s' % username
            return context.come_back(messages.MSG_BAD_KEY, goto=goto)

        return AutoForm.get_namespace(self, resource, context)


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
        context.login(resource)

        # Ok
        message = INFO(u'Operation successful! Welcome.')
        return context.come_back(message, goto='./')



class User_ChangePasswordForgotten(User_ConfirmRegistration):

    description = MSG(u'Please choose a new password for your account')



class User_ResendConfirmation(BaseView):

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



class User_Profile(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'Profile')
    description = MSG(u"User's profile page.")
    icon = 'action_home.png'
    template = '/ui/user/profile.xml'


    def get_namespace(self, resource, context):
        root = context.root
        user = context.user

        ac = resource.get_access_control()

        # The icons menu
        items = []
        for name in ['edit_account', 'edit_preferences', 'edit_password',
                     'tasks']:
            # Get the view & check access rights
            view = resource.get_view(name)
            if view is None:
                continue
            if not ac.is_access_allowed(user, resource, view):
                continue
            # Append
            items.append({
                'url': ';%s' % name,
                'title': view.title,
                'description': getattr(view, 'description', None),
                'icon': resource.get_method_icon(view, size='48x48'),
            })

        # Ok
        is_owner = user is not None and user.name == resource.name
        return {
            'items': items,
            'is_owner_or_admin': is_owner or root.is_admin(user, resource),
            'user_must_confirm': resource.has_property('user_must_confirm')}




class User_EditAccount(DBResource_Edit):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit Account')
    description = MSG(u'Edit your name and email address.')
    icon = 'card.png'
    schema = {
        'timestamp': DateTime(readonly=True),
        'firstname': Unicode,
        'lastname': Unicode,
        'email': Email,
        'password': String}
    widgets = [timestamp_widget,
               TextWidget('firstname', title=MSG(u"First Name")),
               TextWidget('lastname', title=MSG(u"Last Name")),
               TextWidget('email', title=MSG(u"E-mail Address"))]


    def get_widgets(self, resource, context):
        widgets = list(self.widgets)

        # User must confirm?
        if resource.name == context.user.name:
            widgets.append(PasswordWidget('password',
                mandatory=True,
                title=MSG(u"To confirm these changes, "
                          u"you must type your password")))

        return widgets


    def get_value(self, resource, context, name, datatype):
        if name == 'password':
            return None
        return super(User_EditAccount, self).get_value(resource, context,
                name, datatype)


    def action(self, resource, context, form):
        # Check password to confirm changes
        is_same_user = (resource.name == context.user.name)
        if is_same_user:
            password = form['password']
            if not resource.authenticate(password, clear=True):
                context.message = ERROR(
                    u"You mistyped your actual password, your account is"
                    u" not changed.")
                return

        # If the user changes his email, check there is not already other
        # user with the same email in the database.
        email = form['email']
        if email != resource.get_property('email'):
            results = context.root.search(email=email)
            if len(results):
                context.message = ERROR(
                    u'There is another user with the email "{email}", please'
                    u' try again.', email=email).gettext()
                return

        goto = super(User_EditAccount, self).action(resource, context, form)
        if type(context.message) is INFO:
            context.message = INFO(u'Account changed.')
        return goto



class User_EditPreferences(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit Preferences')
    description = MSG(u'Set your preferred language and timezone.')
    icon = 'preferences.png'
    template = '/ui/user/edit_preferences.xml'
    schema = {
        'user_language': String,
        'user_timezone': String}


    def get_namespace(self, resource, context):
        root = context.root

        # Languages
        user_language = resource.get_property('user_language')
        languages = [
            {'code': code,
             'name': get_language_name(code),
             'is_selected': code == user_language}
            for code in root.get_available_languages() ]

        # Timezone
        user_timezone = resource.get_property('user_timezone')
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
    title = MSG(u'Edit Password')
    description = MSG(u'Change your password.')
    icon = 'lock.png'

    schema = freeze({
        'newpass': String(mandatory=True),
        'newpass2': String(mandatory=True)})
    widgets = [
        PasswordWidget('newpass', title=MSG(u'New password')),
        PasswordWidget('newpass2', title=MSG(u'Confirm'))]


    def get_schema(self, resource, context):
        if resource.name != context.user.name:
            return self.schema
        return merge_dicts(self.schema, password=String(mandatory=True))


    def get_widgets(self, resource, context):
        if resource.name != context.user.name:
            return self.widgets
        title = MSG(u'Type your current password')
        return self.widgets + [PasswordWidget('password', title=title)]


    def action(self, resource, context, form):
        # Check password to confirm changes
        is_same_user = (resource.name == context.user.name)
        if is_same_user:
            password = form['password']
            if not resource.authenticate(password, clear=True):
                context.message = ERROR(
                    u"You mistyped your actual password, your account is"
                    u" not changed.")
                return

        # Check the new password matches
        newpass = form['newpass'].strip()
        newpass2 = form['newpass2']
        if newpass != newpass2:
            context.message = ERROR(u"Passwords mismatch, please try again.")
            return

        # Clear confirmation key
        if resource.has_property('user_must_confirm'):
            resource.del_property('user_must_confirm')

        # Set password
        resource.set_password(newpass)

        # Update the cookie if we updated our own password
        if is_same_user:
            context.login(resource)

        # Ok
        context.message = messages.MSG_CHANGES_SAVED



class User_Tasks(STLView):

    access = 'is_allowed_to_edit'
    title = MSG(u'Tasks')
    description = MSG(u'See your pending tasks.')
    icon = 'tasks.png'
    template = '/ui/user/tasks.xml'


    def get_namespace(self, resource, context):
        # 1. Build the query
        query = PhraseQuery('workflow_state', 'pending')
        site_root = context.site_root
        if site_root.parent is not None:
            q2 = OrQuery(
                StartQuery('abspath', '%s/' % site_root.get_abspath()),
                StartQuery('abspath', '%s/' % resource.get_canonical_path()))
            query = AndQuery(query, q2)

        # 2. Build the list of documents
        root = context.root
        documents = []
        for brain in root.search(query).get_documents():
            document = root.get_resource(brain.abspath)
            # Check security
            ac = document.get_access_control()
            if ac.is_allowed_to_view(context.user, document):
                documents.append(
                    {'url': '%s/' % resource.get_pathto(document),
                     'title': document.get_title()})

        return {'documents': documents}



class UserFolder_BrowseContent(Folder_BrowseContent):

    access = 'is_admin'

    search_fields = (Folder_BrowseContent.search_fields
                     + [('username', MSG(u'Login')),
                        ('lastname', MSG(u'Last Name')),
                        ('firstname', MSG(u'First Name'))])
