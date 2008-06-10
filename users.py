# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
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
from base64 import decodestring, encodestring
from copy import deepcopy
from string import Template
from urllib import quote, unquote

# Import from itools
from itools.datatypes import DataType, Email, String, Unicode
from itools.handlers import Folder as BaseFolder
from itools.i18n import get_language_name
from itools.stl import stl
from itools.uri import Path
from itools.web import FormError
from itools.xapian import EqQuery, AndQuery, OrQuery, TextField, KeywordField

# Import from ikaaro
from access import AccessControl
from folder import Folder
from messages import *
from registry import register_object_class, get_object_class
from utils import crypt_password, generate_password



class Password(DataType):

    @staticmethod
    def decode(data):
        return decodestring(unquote(data))


    @staticmethod
    def encode(value):
        return quote(encodestring(value))



class User(AccessControl, Folder):

    class_id = 'user'
    class_version = '20071215'
    class_title = 'User'
    class_icon16 = 'icons/16x16/user.png'
    class_icon48 = 'icons/48x48/user.png'
    class_views = [
        ['profile'],
        ['browse_content?mode=list',
         'browse_content?mode=image'],
        ['new_resource_form'],
        ['edit_account_form', 'edit_language_form', 'edit_password_form'],
        ['tasks_list']]


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
        request = context.request
        expires = request.form.get('iAuthExpires', None)
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
            msg = u'Confirmation sended!'
        else:
            msg = u'User has already confirm his registration!'
        return context.come_back(msg)


    confirm_registration_form__access__ = True
    def confirm_registration_form(self, context):
        # Check register key
        must_confirm = self.get_property('user_must_confirm')
        username = context.get_form_value('username', default='')
        if must_confirm is None:
            return context.come_back(MSG_REGISTERED,
                    goto='/;login_form?username=%s' % username)
        elif context.get_form_value('key') != must_confirm:
            return context.come_back(MSG_BAD_KEY,
                    goto='/;login_form?username=%s' % username)

        namespace = {'key': must_confirm,
                     'username': self.get_login_name()}

        handler = self.get_object('/ui/user/confirm_registration.xml')
        return stl(handler, namespace)


    confirm_registration__access__ = True
    def confirm_registration(self, context):
        keep = ['key']
        register_fields = {'newpass': String(mandatory=True),
                           'newpass2': String(mandatory=True)}

        # Check register key
        must_confirm = self.get_property('user_must_confirm')
        if context.get_form_value('key') != must_confirm:
            return context.come_back(MSG_BAD_KEY)

        # Check input data
        try:
            form = context.check_form_input(register_fields)
        except FormError:
            return context.come_back(MSG_MISSING_OR_INVALID, keep=keep)

        # Check passwords
        password = form['newpass']
        password2 = form['newpass2']
        if password != password2:
            return context.come_back(MSG_PASSWORD_MISMATCH, keep=keep)

        # Set user
        self.set_password(password)
        self.del_property('user_must_confirm')

        # Set cookie
        self.set_auth_cookie(context, password)

        message = u'Operation successful ! Welcome.'
        goto = "./;%s" % self.get_firstview()
        return context.come_back(message, goto=goto)


    #######################################################################
    # Profile
    profile__access__ = 'is_allowed_to_view'
    profile__label__ = u'Profile'
    profile__icon__ = 'action_home.png'
    def profile(self, context):
        root = context.root
        user = context.user

        namespace = {}
        namespace['title'] = self.get_title()
        # Owner
        is_owner = user is not None and user.name == self.name
        namespace['is_owner'] = is_owner
        # Owner or Admin
        namespace['is_owner_or_admin'] = is_owner or root.is_admin(user, self)
        # Must confirm ?
        namespace['user_must_confirm'] = self.has_property('user_must_confirm')

        handler = self.get_object('/ui/user/profile.xml')
        return stl(handler, namespace)


    #######################################################################
    # Edit Language
    edit_language_form__access__ = 'is_allowed_to_edit'
    edit_language_form__label__ = u'Edit'
    edit_language_form__sublabel__ = u'Language'
    edit_language_form__icon__ = 'skin.png'
    def edit_language_form(self, context):
        root = context.root
        user = context.user

        # Build the namespace
        namespace = {}

        # Languages
        languages = []
        user_language = self.get_property('user_language')
        for language_code in root.get_available_languages():
            languages.append({'code': language_code,
                              'name': get_language_name(language_code),
                              'is_selected': language_code == user_language})
        namespace['languages'] = languages

        handler = self.get_object('/ui/user/edit_language_form.xml')
        return stl(handler, namespace)


    edit_language__access__ = 'is_allowed_to_edit'
    def edit_language(self, context):
        value = context.get_form_value('user_language')
        self.set_property('user_language', value)

        return context.come_back(u'Application preferences changed.')


    #######################################################################
    # Edit account
    edit_account_form__access__ = 'is_allowed_to_edit'
    edit_account_form__label__ = u'Edit'
    edit_account_form__sublabel__ = u'Account'
    edit_account_form__icon__ = 'settings.png'
    def edit_account_form(self, context):
        # Build the namespace
        namespace = {}
        namespace['firstname'] = self.get_property('firstname')
        namespace['lastname'] = self.get_property('lastname')
        namespace['email'] = self.get_property('email')
        # Ask for password to confirm the changes
        if self.name != context.user.name:
            namespace['must_confirm'] = False
        else:
            namespace['must_confirm'] = True

        handler = self.get_object('/ui/user/edit_account.xml')
        return stl(handler, namespace)


    edit_account__access__ = 'is_allowed_to_edit'
    def edit_account(self, context):
        # Check password to confirm changes
        password = context.get_form_value('password')
        user = context.user
        if self.name == user.name:
            if not self.authenticate(password):
                return context.come_back(
                    u"You mistyped your actual password, your account is"
                    u" not changed.")

        # Check the email is good
        email = context.get_form_value('email', type=Email)
        if not Email.is_valid(email):
            return context.come_back(MSG_INVALID_EMAIL)

        root = context.root
        results = root.search(email=email)
        if results.get_n_documents():
            message = (u'There is another user with the email "%s", '
                       u'please try again')

        # Save changes
        value = context.get_form_value('firstname', type=Unicode)
        self.set_property('firstname', value)
        value = context.get_form_value('lastname', type=Unicode)
        self.set_property('lastname', value)
        value = context.get_form_value('email', type=Email)
        self.set_property('email', value)

        return context.come_back(u'Account changed.')


    #######################################################################
    # Edit password
    edit_password_form__access__ = 'is_allowed_to_edit'
    edit_password_form__label__ = u'Edit'
    edit_password_form__sublabel__ = u'Password'
    edit_password_form__icon__ = 'lock.png'
    def edit_password_form(self, context):
        user = context.user

        # Build the namespace
        namespace = {}
        if self.name != user.name:
            namespace['must_confirm'] = False
        else:
            namespace['must_confirm'] = True

        handler = self.get_object('/ui/user/edit_password.xml')
        return stl(handler, namespace)


    edit_password__access__ = 'is_allowed_to_edit'
    def edit_password(self, context):
        newpass = context.get_form_value('newpass')
        newpass2 = context.get_form_value('newpass2')
        password = context.get_form_value('password')
        user = context.user

        # Check input
        if self.name == user.name:
            if not self.authenticate(password):
                return context.come_back(u"You mistyped your actual password, "
                                         u"your account is not changed.")

        newpass = newpass.strip()
        if not newpass:
            return context.come_back(u'Password empty, please type one.')

        if newpass != newpass2:
            return context.come_back(u"Passwords mismatch, please try again.")

        # Clear confirmation key
        if self.has_property('user_must_confirm'):
            self.del_property('user_must_confirm')

        # Set password
        self.set_password(newpass)

        # Update the cookie if we updated our own password
        if self.name == user.name:
            self.set_auth_cookie(context, newpass)

        return context.come_back(u'Password changed.')


    #######################################################################
    # Tasks
    tasks_list__access__ = 'is_allowed_to_edit'
    tasks_list__label__ = u'Tasks'
    tasks_list__icon__ = 'tasks.png'
    def tasks_list(self, context):
        root = context.root
        user = context.user
        site_root = self.get_site_root()
        namespace = {}
        documents = []

        q1 = EqQuery('workflow_state', 'pending')
        q2 = OrQuery(EqQuery('paths', str(site_root.get_abspath())),
                     EqQuery('paths', str(self.get_canonical_path())))
        query = AndQuery(q1, q2)

        for brain in root.search(query).get_documents():
            document = root.get_object(brain.abspath)
            # Check security
            ac = document.get_access_control()
            if not ac.is_allowed_to_view(user, document):
                continue
            documents.append({'url': '%s/;%s' % (self.get_pathto(document),
                                                 document.get_firstview()),
                             'title': document.get_title()})
        namespace['documents'] = documents

        handler = self.get_object('/ui/user/tasks.xml')
        return stl(handler, namespace)


    #######################################################################
    # Update
    #######################################################################
    def update_20071215(self, remove=None):
        if remove is None:
            remove = [
                'id', 'owner', 'dc:language', 'dc:title', 'ikaaro:history',
                'ikaaro:wf_transition', 'ikaaro:user_theme']
        Folder.update_20071215(self, remove=remove)



class UserFolder(Folder):

    class_id = 'users'
    class_version = '20071215'
    class_icon16 = 'icons/16x16/userfolder.png'
    class_icon48 = 'icons/48x48/userfolder.png'
    class_views = [['view'],
                   ['browse_content?mode=list'],
                   ['edit_metadata_form']]


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

    edit_metadata_form__access__ = 'is_admin'
    edit_metadata__access__ = 'is_admin'


    #######################################################################
    # View
    view__access__ = 'is_admin'
    view__label__ = u'View'
    view__icon__ = 'view.png'
    def view(self, context):
        message = (u'To manage the users please go '
                   u'<a href="/;permissions_form">here</a>.')
        return self.gettext(message).encode('utf-8')



###########################################################################
# Register
###########################################################################
register_object_class(UserFolder)
register_object_class(User)
