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
from string import Template

# Import from itools
from itools.datatypes import Email, String, Unicode
from itools.gettext import MSG
from itools.uri import Path
from itools.xapian import TextField, KeywordField

# Import from ikaaro
from access import AccessControl
from datatypes import Password
from folder import Folder
from registry import register_object_class, get_object_class
from resource_views import DBResourceEditMetadata
from user_views import UserConfirmRegistration, UserProfile, UserEditAccount
from user_views import UserEditPreferences, UserEditPassword, UserTasks
from utils import crypt_password, generate_password
from views import MessageView



class User(AccessControl, Folder):

    class_id = 'user'
    class_version = '20071215'
    class_title = MSG(u'User')
    class_icon16 = 'icons/16x16/user.png'
    class_icon48 = 'icons/48x48/user.png'
    class_views = ['profile', 'browse_content', 'preview_content',
                   'new_resource', 'edit_account', 'edit_preferences',
                   'edit_password', 'tasks']


    ########################################################################
    # Metadata
    ########################################################################
    @classmethod
    def get_metadata_schema(cls):
        return {
            'firstname': Unicode,
            'lastname': Unicode,
            'email': Email,
            'password': Password,
            'user_language': String(default='en'),
            'user_must_confirm': String,
            # Backwards compatibility
            'username': String,
        }


    ########################################################################
    # Indexing
    ########################################################################
    def get_catalog_fields(self):
        fields = Folder.get_catalog_fields(self)
        fields += [KeywordField('email', is_stored=True),
                   TextField('lastname', is_stored=True),
                   TextField('firstname', is_stored=True),
                   # Login Name
                   KeywordField('username', is_stored=True)]
        return fields


    def get_catalog_values(self):
        values = Folder.get_catalog_values(self)
        values['email'] = self.get_property('email')
        values['username'] = self.get_login_name()
        values['firstname'] = self.get_property('firstname')
        values['lastname'] = self.get_property('lastname')
        return values


    def get_canonical_path(self):
        return Path('/users/%s' % self.name)


    ########################################################################
    # API
    ########################################################################
    def get_title(self, language=None):
        firstname = self.get_property('firstname')
        lastname = self.get_property('lastname')
        if firstname:
            if lastname:
                return '%s %s' % (firstname, lastname)
            return firstname
        if lastname:
            return lastname
        return self.get_login_name()


    def get_login_name(self):
        # FIXME Check first the username (for compatibility with 0.14)
        username = self.get_property('username')
        if username:
            return username
        return self.get_property('email')


    def set_password(self, password):
        crypted = crypt_password(password)
        self.set_property('password', crypted)


    def authenticate(self, password):
        if self.get_property('user_must_confirm'):
            return False
        # Is password crypted?
        if password == self.get_property('password'):
            return True
        # Is password clear?
        crypted = crypt_password(password)
        return crypted == self.get_property('password')


    def get_groups(self):
        """Returns all the role aware handlers where this user is a member.
        """
        root = self.get_root()
        if root is None:
            return ()

        results = root.search(is_role_aware=True, members=self.name)
        groups = [ x.abspath for x in results.get_documents() ]
        return tuple(groups)


    def set_auth_cookie(self, context, password):
        username = str(self.name)
        crypted = crypt_password(password)
        cookie = Password.encode('%s:%s' % (username, crypted))
        expires = context.request.get_parameter('iAuthExpires')
        if expires is None:
            context.set_cookie('__ac', cookie, path='/')
        else:
            context.set_cookie('__ac', cookie, path='/', expires=expires)


    ########################################################################
    # Access control
    def is_self_or_admin(self, user, object):
        # You are nobody here, ha ha ha
        if user is None:
            return False

        # In my home I am the king
        if self.name == user.name:
            return True

        # The all-powerfull
        return self.is_admin(user, object)


    is_allowed_to_edit = is_self_or_admin


    #######################################################################
    # User interface
    #######################################################################

    #######################################################################
    # Registration
    def send_confirmation(self, context, email):
        # Set the confirmation key
        key = generate_password(30)
        self.set_property('user_must_confirm', key)

        # Build the confirmation link
        confirm_url = deepcopy(context.uri)
        path = '/users/%s/;confirm_registration_form' % self.name
        confirm_url.path = Path(path)
        confirm_url.query = {'key': key, 'username': self.get_login_name()}
        confirm_url = str(confirm_url)

        # Build the email
        subject = u"Confirmation required"
        subject = self.gettext(subject)
        body = self.gettext(
            u"To confirm your identity click the link:\n"
            u"\n"
            u"  $confirm_url")
        body = Template(body).substitute({'confirm_url': confirm_url})
        # Send
        context.root.send_email(email, subject, text=body)


    resend_confirmation__access__ = 'is_admin'
    def resend_confirmation(self, context):
        must_confirm = self.has_property('user_must_confirm')
        if must_confirm:
            context.commit = True
            self.send_confirmation(context, self.get_property('email'))
            msg = MSG(u'Confirmation sended!')
        else:
            msg = MSG(u'User has already confirm his registration!')
        return context.come_back(msg)


    #######################################################################
    # Views
    confirm_registration = UserConfirmRegistration()
    profile = UserProfile()
    edit_account = UserEditAccount()
    edit_preferences = UserEditPreferences()
    edit_password = UserEditPassword()
    tasks = UserTasks()



class UserFolder(Folder):

    class_id = 'users'
    class_version = '20071215'
    class_icon16 = 'icons/16x16/userfolder.png'
    class_icon48 = 'icons/48x48/userfolder.png'
    class_views = ['view', 'browse_content', 'edit_metadata']


    def get_document_types(self):
        return [get_object_class('user')]


    #######################################################################
    # API
    #######################################################################
    def set_user(self, email=None, password=None):
        # Calculate the user id
        ids = []
        for key in self.get_names():
            try:
                key = int(key)
            except ValueError:
                continue
            ids.append(key)
        if ids:
            ids.sort()
            user_id = str(ids[-1] + 1)
        else:
            user_id = '0'

        # Add the user
        cls = get_object_class('user')
        user = cls.make_object(cls, self, user_id)
        # Set the email and paswword
        if email is not None:
            user.set_property('email', email)
        if password is not None:
            user.set_password(password)

        # Return the user
        return user


    def get_usernames(self):
        """Return all user names."""
        names = self._get_names()
        return frozenset(names)


    #######################################################################
    # Back-Office
    #######################################################################
    browse_content__access__ = 'is_admin'
    rename_form__access__ = False
    rename__access__ = False
    cut__access__ = False
    #remove__access__ = False
    copy__access__ = False
    paste__access__ = False


    edit_metadata = DBResourceEditMetadata(access='is_admin')


    #######################################################################
    # View
    view = MessageView(
        access='is_admin',
        title=MSG(u'View'),
        icon='view.png',
        message = MSG(u'To manage the users please go '
                      u'<a href="/;permissions">here</a>.'))



###########################################################################
# Register
###########################################################################
register_object_class(UserFolder)
register_object_class(User)
