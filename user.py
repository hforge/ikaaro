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
from itools.datatypes import String
from itools.gettext import MSG
from itools.log import log_warning
from itools.uri import Path, Reference
from itools.web import INFO

# Import from ikaaro
from autoedit import AutoEdit
from fields import Char_Field, Email_Field, Password_Field, Text_Field
from fields import File_Field
from folder import Folder
from registry import get_resource_class
from resource_ import DBResource
from user_views import User_ConfirmRegistration, User_EditAccount
from user_views import User_EditPassword, User_EditPreferences, User_Profile
from user_views import User_ResendConfirmation, User_Tasks
from user_views import User_ChangePasswordForgotten, UserFolder_BrowseContent
from utils import get_secure_hash, generate_password
from views import MessageView



class User(DBResource):

    class_id = 'user'
    class_version = '20081217'
    class_title = MSG(u'User')
    class_icon16 = 'icons/16x16/user.png'
    class_icon48 = 'icons/48x48/user.png'
    class_views = ['profile', 'edit_account', 'edit_preferences',
                   'edit_password', 'tasks']


    ########################################################################
    # Metadata
    ########################################################################
    fields = ['firstname', 'lastname', 'email', 'password', 'avatar',
              'user_language', 'user_timezone', 'user_must_confirm',
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
    user_must_confirm = Char_Field
    groups = Char_Field(multiple=True, indexed=True)
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
        email = self.get_property('email')
        if email and '@' in email:
            values['email_domain'] = email.split('@', 1)[1]

        # username (overrides default)
        values['username'] = self.get_login_name()

        # groups
        values['groups'] = self.get_property('groups')

        return values


    def get_links(self):
        return set(self.get_property('groups'))


    ########################################################################
    # API / Authentication
    ########################################################################
    def get_user_id(self):
        # Used by itools.web
        return str(self.name)


    def get_auth_token(self):
        # Used by itools.web
        return self.get_property('password')


    def set_password(self, password):
        secure_hash = get_secure_hash(password)
        self.set_property('password', secure_hash)


    def authenticate(self, password, clear=None):
        if clear is not None:
            log_warning('The "clear" param is DEPRECATED', domain='ikaaro')

        secure_hash = get_secure_hash(password)
        return secure_hash == self.get_property('password')


    def set_auth_cookie(self, context, password):
        msg = "user.set_auth_cookie is DEPRECATED, use context.login(user)"
        log_warning(msg, domain='ikaaro')
        context.login(self)


    ########################################################################
    # API
    ########################################################################
    def get_owner(self):
        return self.name


    def get_title(self, language=None):
        firstname = self.get_value('firstname')
        lastname = self.get_property('lastname')
        if firstname:
            if lastname:
                return '%s %s' % (firstname, lastname)
            return firstname
        if lastname:
            return lastname
        return self.get_login_name().decode('utf-8')


    login_name_property = 'email'
    def get_login_name(self):
        return self.get_property(self.login_name_property)


    def get_groups(self):
        """Returns all the role aware handlers where this user is a member.
        """
        return tuple(self.get_property('groups'))


    def get_timezone(self):
        return self.get_property('user_timezone')


    ########################################################################
    # Email: Register confirmation & Password forgotten
    ########################################################################

    confirmation_subject = MSG(u"Confirmation required")
    confirmation_txt = MSG(u"To confirm your identity, click the link:"
                           u"\n"
                           u"\n {uri}")
    def send_confirmation(self, context, email):
        self.send_confirm_url(context, email, self.confirmation_subject,
            self.confirmation_txt, ';confirm_registration')


    registration_subject = MSG(u"Registration confirmed")
    registration_txt = MSG(u"You are now registered as users of: {site_name}.\n"
                           u"You can follow this link {site_uri} to access "
                           u"to the site.")
    def send_registration(self, context, email):
        site_name = context.site_root.get_title()
        uri = context.uri
        site_uri = Reference(uri.scheme, uri.authority, '/', {}, None)
        text = self.registration_txt.gettext(site_name=site_name,
                                             site_uri=site_uri)
        context.root.send_email(email, self.registration_subject.gettext(),
                                text=text)


    forgotten_subject = MSG(u"Choose a new password")
    forgotten_txt = MSG(u"To choose a new password, click the link:"
                        u"\n"
                        u"\n {uri}")
    def send_forgotten_password(self, context, email):
        self.send_confirm_url(context, email, self.forgotten_subject,
            self.forgotten_txt, ';change_password_forgotten')


    def send_confirm_url(self, context, email, subject, text, view):
        # Set the confirmation key
        if self.has_property('user_must_confirm'):
            key = self.get_property('user_must_confirm')
        else:
            key = generate_password(30)
            self.set_property('user_must_confirm', key)

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
    tasks = User_Tasks()



class UserFolder(Folder):

    class_id = 'users'
    class_title = MSG(u'User Folder')
    class_icon16 = 'icons/16x16/userfolder.png'
    class_icon48 = 'icons/48x48/userfolder.png'
    class_views = ['view', 'browse_content', 'edit']
    is_content = False


    def get_document_types(self):
        return [get_resource_class('user')]


    #######################################################################
    # API
    #######################################################################
    def get_next_user_id(self):
        ids = []
        for key in self.get_names():
            try:
                key = int(key)
            except ValueError:
                continue
            ids.append(key)
        if ids:
            user_id = str(max(ids) + 1)
        else:
            user_id = '0'
        return user_id


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
                     u'<a href="/;browse_users">here</a>.'))


# Register
register_field('email_domain', String(indexed=True, stored=True))
