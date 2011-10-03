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

# Import from the Standard Library
from copy import deepcopy

# Import from itools
from itools.database import register_field
from itools.datatypes import Enumerate, String
from itools.gettext import MSG
from itools.uri import Path, Reference
from itools.web import INFO, get_context

# Import from ikaaro
from autoedit import AutoEdit
from autoform import CheckboxWidget
from fields import Char_Field, Email_Field, Password_Field, Text_Field
from fields import File_Field, Select_Field, URI_Field
from folder import Folder
from resource_ import DBResource
from user_views import User_ConfirmRegistration, User_EditAccount
from user_views import User_EditPassword, User_EditPreferences, User_Profile
from user_views import User_ResendConfirmation
from user_views import User_ChangePasswordForgotten, UserFolder_BrowseContent
from utils import get_secure_hash, generate_password
from views import MessageView


class UserGroups_Datatype(Enumerate):

    _resource_path = '/config/groups'
    def get_options(self):
        resource = get_context().root.get_resource(self._resource_path)
        return [ {'name': str(x.abspath), 'value': x.get_title()}
                 for x in resource.get_resources() ]


class UserGroups_Field(URI_Field):

    datatype = UserGroups_Datatype
    indexed = True
    multiple = True
    title = MSG(u'Groups')
    widget = CheckboxWidget



class UserState_Field(Select_Field):

    parameters_schema = {'key': String}
    default = 'active'
    options = [
        {'name': 'active', 'value': MSG(u'Active')},
        {'name': 'pending', 'value': MSG(u'Pending confirmation')},
        {'name': 'inactive', 'value': MSG(u'Inactive')}]



class User(DBResource):

    class_id = 'user'
    class_version = '20081217'
    class_title = MSG(u'User')
    class_icon16 = 'icons/16x16/user.png'
    class_icon48 = 'icons/48x48/user.png'
    class_views = ['profile', 'edit_account', 'edit_preferences',
                   'edit_password', 'edit_groups']


    ########################################################################
    # Metadata
    ########################################################################
    fields = ['firstname', 'lastname', 'email', 'password', 'avatar',
              'user_language', 'user_timezone', 'user_state',
              'groups', 'username']
    firstname = Text_Field(multilingual=False, indexed=True, stored=True,
                           title=MSG(u'First Name'))
    lastname = Text_Field(multilingual=False, indexed=True, stored=True,
                          title=MSG(u'Last Name'))
    email = Email_Field(indexed=True, stored=True, required=True,
                        title=MSG(u'E-mail Address'))
    password = Password_Field
    avatar = File_Field(title=MSG(u'Avatar'))
    user_language = Char_Field
    user_timezone = Char_Field
    user_state = UserState_Field
    groups = UserGroups_Field
    # Metadata (backwards compatibility)
    username = Char_Field(indexed=True, stored=True)

    # Remove some fields
    title = None
    description = None
    subject = None
    text = None


    ########################################################################
    # Indexing
    ########################################################################
    def get_catalog_values(self):
        values = super(User, self).get_catalog_values()

        # email domain
        email = self.get_value('email')
        if email and '@' in email:
            values['email_domain'] = email.split('@', 1)[1]

        # username (overrides default)
        values['username'] = self.get_login_name()

        # groups
        values['groups'] = self.get_value('groups')

        return values


    ########################################################################
    # API / Authentication
    ########################################################################
    def get_user_id(self):
        # Used by itools.web
        return str(self.name)


    def get_auth_token(self):
        # Used by itools.web
        return self.get_value('password')


    def authenticate(self, password):
        secure_hash = get_secure_hash(password)
        return secure_hash == self.get_value('password')


    ########################################################################
    # API
    ########################################################################
    def get_owner(self):
        return str(self.abspath)


    def get_title(self, language=None):
        firstname = self.get_value('firstname')
        lastname = self.get_value('lastname')
        if firstname:
            if lastname:
                return '%s %s' % (firstname, lastname)
            return firstname
        if lastname:
            return lastname
        return self.get_login_name().decode('utf-8')


    login_name_property = 'email'
    def get_login_name(self):
        return self.get_value(self.login_name_property)


    def get_timezone(self):
        return self.get_value('user_timezone')


    def account_is_completed(self):
        for name, field in self.get_fields():
            if field.required and not self.has_property(name):
                return False
        return True

    ########################################################################
    # Email: Register confirmation & Password forgotten
    ########################################################################
    already_registered_subject = MSG(u"Already registered")
    already_registered_txt = MSG(u"You already have an account:\n"
                                 u"\n {uri}")
    def send_already_registered(self, context, email):
        uri = context.uri
        uri = uri.resolve('%s/;login?loginname=%s' % (self.abspath, email))
        text = self.already_registered_txt.gettext(uri=uri)
        # Send email
        root = context.root
        root.send_email(email, self.already_registered_subject, text=text)


    confirmation_subject = MSG(u"Confirmation required")
    confirmation_txt = MSG(u"To confirm your identity, click the link:\n"
                           u"\n {uri}")
    def send_confirmation(self, context, email):
        self.send_confirm_url(context, email, self.confirmation_subject,
            self.confirmation_txt, ';confirm_registration')


    registration_subject = MSG(u"Registration confirmed")
    registration_txt = MSG(
        u"You are now registered as users of: {site_name}.\n"
        u"You can follow this link {site_uri} to access to the site.")
    def send_registration(self, context, email):
        root = context.root
        uri = context.uri
        site_uri = Reference(uri.scheme, uri.authority, '/', {}, None)
        text = self.registration_txt.gettext(site_name=root.get_title(),
                                             site_uri=site_uri)
        root.send_email(email, self.registration_subject.gettext(), text=text)


    forgotten_subject = MSG(u"Choose a new password")
    forgotten_txt = MSG(u"To choose a new password, click the link:\n"
                        u"\n {uri}")
    def send_forgotten_password(self, context, email):
        self.send_confirm_url(context, email, self.forgotten_subject,
            self.forgotten_txt, ';change_password_forgotten')


    def send_confirm_url(self, context, email, subject, text, view):
        # Set the confirmation key
        state = self.get_property('user_state')
        if state.value == 'pending':
            key = state.get_parameter('key')
        else:
            key = generate_password(30)
            self.set_value('user_state', 'pending', key=key)

        # Build the confirmation link
        confirm_url = deepcopy(context.uri)
        path = '/users/%s/%s' % (self.name, view)
        confirm_url.path = Path(path)
        confirm_url.query = {'key': key, 'username': self.get_login_name()}
        confirm_url = str(confirm_url)
        text = text.gettext(uri=confirm_url)
        context.root.send_email(email, subject.gettext(), text=text)


    #######################################################################
    # Views
    #######################################################################
    resend_confirmation = User_ResendConfirmation()
    confirm_registration = User_ConfirmRegistration()
    change_password_forgotten = User_ChangePasswordForgotten()
    profile = User_Profile()
    edit_account = User_EditAccount()
    edit_preferences = User_EditPreferences()
    edit_password = User_EditPassword()
    edit_groups = AutoEdit(access='is_admin', fields=['groups'],
                           title=MSG(u'Edit groups'))



class UserFolder(Folder):

    class_id = 'users'
    class_title = MSG(u'User Folder')
    class_icon16 = 'icons/16x16/userfolder.png'
    class_icon48 = 'icons/48x48/userfolder.png'
    class_views = ['view', 'browse_content', 'edit']
    is_content = False


    def get_document_types(self):
        return [self.database.get_resource_class('user')]


    #######################################################################
    # API
    #######################################################################
    def get_usernames(self):
        """Return all user names."""
        names = self._get_names()
        return frozenset(names)


    #######################################################################
    # Back-Office
    #######################################################################
    browse_content = UserFolder_BrowseContent()
    edit = AutoEdit(access='is_admin')


    #######################################################################
    # View
    view = MessageView(
        access='is_admin',
        title=MSG(u'View'),
        icon='view.png',
        message=INFO(u'To manage the users please go '
                     u'<a href="/config/users">here</a>.'))


# Register
register_field('email_domain', String(indexed=True, stored=True))
