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
from copy import deepcopy
from string import Template

# Import from itools
from itools.datatypes import DataType, Email, String, Unicode
from itools.gettext import MSG
from itools.handlers import Folder as BaseFolder
from itools.i18n import get_language_name
from itools.stl import stl
from itools.uri import Path
from itools.web import FormError, STLView, STLForm
from itools.xapian import EqQuery, AndQuery, OrQuery, TextField, KeywordField

# Import from ikaaro
from access import AccessControl
from base import MetadataForm
from datatypes import Password
from folder import Folder
from messages import *
from registry import register_object_class, get_object_class
from utils import crypt_password, generate_password


###########################################################################
# Views
###########################################################################
class ProfileView(STLView):

    access = 'is_allowed_to_view'
    tab_label = MSG(u'Profile')
    tab_icon = 'action_home.png'
    template = '/ui/user/profile.xml'


    def get_namespace(self, model, context):
        root = context.root
        user = context.user

        is_owner = user is not None and user.name == model.name
        return {
            'title': model.get_title(),
            'is_owner': is_owner,
            'is_owner_or_admin': is_owner or root.is_admin(user, model),
            'user_must_confirm': model.has_property('user_must_confirm'),
        }



class AccountForm(STLForm):

    access = 'is_allowed_to_edit'
    tab_label = MSG(u'Edit')
    tab_sublabel = MSG(u'Account')
    page_title = MSG(u'Edit your personal data')
    tab_icon = 'settings.png'
    template = '/ui/user/edit_account.xml'
    schema = {
        'password': String,
        'email': Email,
        'firstname': Unicode,
        'lastname': Unicode,
    }


    def get_namespace(self, model, context):
        return {
            'firstname': model.get_property('firstname'),
            'lastname': model.get_property('lastname'),
            'email': model.get_property('email'),
            'must_confirm': (model.name == context.user.name),
        }


    def action(self, model, context, form):
        firstname = form['firstname']
        lastname = form['lastname']
        email = form['email']

        # Check password to confirm changes
        is_same_user = (model.name == context.user.name)
        if is_same_user:
            password = form['password']
            if not model.authenticate(password):
                context.message = (
                    u"You mistyped your actual password, your account is"
                    u" not changed.")
                return

        # If the user changes his email, check there is not already other
        # user with the same email in the database.
        if email != model.get_property('email'):
            results = context.root.search(email=email)
            if results.get_n_documents():
                context.message = model.gettext(
                    u'There is another user with the email "${email}", please'
                    u' try again.', email=email)
                return

        # Save changes
        model.set_property('firstname', firstname)
        model.set_property('lastname', lastname)
        model.set_property('email', email)
        # Ok
        context.message = u'Account changed.'



class PreferencesForm(STLForm):

    access = 'is_allowed_to_edit'
    tab_label = MSG(u'Edit')
    tab_sublabel = MSG(u'Preferences')
    tab_icon = 'skin.png'
    page_title = tab_sublabel
    template = '/ui/user/edit_language_form.xml'
    schema = {
        'user_language': String(mandatory=True),
    }


    def get_namespace(self, model, context):
        root = context.root
        user = context.user

        # Languages
        user_language = model.get_property('user_language')
        languages = [
            {'code': code, 'name': get_language_name(code),
             'is_selected': code == user_language}
            for code in root.get_available_languages() ]

        return {'languages': languages}


    def action(self, model, context, form):
        value = form['user_language']
        model.set_property('user_language', value)
        # Ok
        context.message = u'Application preferences changed.'



class PasswordForm(STLForm):

    access = 'is_allowed_to_edit'
    tab_label = MSG(u'Edit')
    tab_sublabel = MSG(u'Password')
    tab_icon = 'lock.png'
    page_title = MSG(u'Change you password')
    template = '/ui/user/edit_password.xml'
    schema = {
        'newpass': String(mandatory=True),
        'newpass2': String(mandatory=True),
        'password': String,
    }


    def get_namespace(self, model, context):
        user = context.user
        return {
            'must_confirm': (model.name == user.name)
        }


    def action(self, model, context, form):
        newpass = form['newpass'].strip()
        newpass2 = form['newpass2']

        # Check password to confirm changes
        is_same_user = (model.name == context.user.name)
        if is_same_user:
            password = form['password']
            if not model.authenticate(password):
                context.message = (
                    u"You mistyped your actual password, your account is"
                    u" not changed.")
                return

        # Check the new password matches
        if newpass != newpass2:
            context.message = u"Passwords mismatch, please try again."
            return

        # Clear confirmation key
        if model.has_property('user_must_confirm'):
            model.del_property('user_must_confirm')

        # Set password
        model.set_password(newpass)

        # Update the cookie if we updated our own password
        if is_same_user:
            model.set_auth_cookie(context, newpass)

        # Ok
        context.message = u'Password changed.'



class TasksView(STLView):

    access = 'is_allowed_to_edit'
    tab_label = MSG(u'Tasks')
    tab_icon = 'tasks.png'
    page_title = MSG(u'Tasks')
    template = '/ui/user/tasks.xml'


    def get_namespace(self, model, context):
        root = context.root
        user = context.user

        # Build the query
        site_root = model.get_site_root()
        q1 = EqQuery('workflow_state', 'pending')
        q2 = OrQuery(EqQuery('paths', str(site_root.get_abspath())),
                     EqQuery('paths', str(model.get_canonical_path())))
        query = AndQuery(q1, q2)

        # Build the list of documents
        documents = []
        for brain in root.search(query).get_documents():
            document = root.get_object(brain.abspath)
            # Check security
            ac = document.get_access_control()
            if not ac.is_allowed_to_view(user, document):
                continue
            # Append
            firstview = document.get_firstview()
            documents.append(
                {'url': '%s/;%s' % (model.get_pathto(document), firstview),
                 'title': document.get_title()})

        return {'documents': documents}



###########################################################################
# Model
###########################################################################
class User(AccessControl, Folder):

    class_id = 'user'
    class_version = '20071215'
    class_title = MSG(u'User')
    class_icon16 = 'icons/16x16/user.png'
    class_icon48 = 'icons/48x48/user.png'
    class_views = [
        ['profile'],
        ['browse_content', 'preview_content'],
        ['new_resource'],
        ['edit_account', 'edit_preferences', 'edit_password'],
        ['tasks']]


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
                    goto='/;login?username=%s' % username)
        elif context.get_form_value('key') != must_confirm:
            return context.come_back(MSG_BAD_KEY,
                    goto='/;login?username=%s' % username)

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
    profile = ProfileView()
    edit_account = AccountForm()
    edit_preferences = PreferencesForm()
    edit_password = PasswordForm()
    tasks = TasksView()



class UserFolder(Folder):

    class_id = 'users'
    class_version = '20071215'
    class_icon16 = 'icons/16x16/userfolder.png'
    class_icon48 = 'icons/48x48/userfolder.png'
    class_views = [['view'],
                   ['browse_content'],
                   ['edit_metadata']]


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


    edit_metadata = MetadataForm(access='is_admin')


    #######################################################################
    # View
    view__access__ = 'is_admin'
    view__label__ = u'View'
    view__icon__ = 'view.png'
    def view(self, context):
        message = (
            u'To manage the users please go <a href="/;permissions">here</a>.')
        return self.gettext(message).encode('utf-8')



###########################################################################
# Register
###########################################################################
register_object_class(UserFolder)
register_object_class(User)
