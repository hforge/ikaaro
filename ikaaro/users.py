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
from itools.database import register_field
from itools.datatypes import Boolean, String
from itools.gettext import MSG
from itools.web import ERROR, get_context

# Import from ikaaro
from .autoedit import AutoEdit
from .config import Configuration
from .enumerates import UserGroups_Datatype
from .fields import Char_Field, Datetime_Field, Email_Field, File_Field
from .fields import Password_Field, SelectAbspath_Field, Select_Field, Text_Field
from .folder import Folder
from .messages import MSG_LOGIN_WRONG_NAME_OR_PASSWORD
from .users_views import User_ConfirmRegistration, User_EditAccount
from .users_views import User_EditPassword, User_EditPreferences, User_Profile
from .users_views import User_ResendConfirmation, User_ChangePasswordForgotten
from .users_views import Users_Browse, Users_AddUser
from .utils import get_secure_hash, generate_password
from .widgets import CheckboxWidget


class Lastlog_Field(Datetime_Field):

    parameters_schema = {'success': Boolean}
    readonly = True
    multiple = True


class UserGroups_Field(SelectAbspath_Field):

    datatype = UserGroups_Datatype()
    indexed = True
    multiple = True
    title = MSG('Groups')
    widget = CheckboxWidget


    def access(self, mode, resource):
        if mode == 'read':
            return True

        context = get_context()
        return context.root.is_admin(context.user, resource)


class Firstname_Field(Text_Field):

    title = MSG('First Name')
    multilingual = False
    indexed = True
    stored = True


class Lastname_Field(Text_Field):

    title = MSG('Last Name')
    multilingual = False
    indexed = True
    stored = True



class UserState_Field(Select_Field):

    parameters_schema = {'key': String()}
    default = 'active'
    options = [
        {'name': 'active', 'value': MSG('Active')},
        {'name': 'pending', 'value': MSG('Pending confirmation')},
        {'name': 'inactive', 'value': MSG('Inactive')}]


class UserEmail_Field(Email_Field):

    title = MSG('E-mail Address')
    indexed = True
    stored = True
    required = True
    unique = True
    encrypted = True


class UserPassword_Field(Password_Field):

    multiple = True



class User(Folder):

    class_id = 'user'
    class_version = '20081217'
    class_title = MSG('User')
    class_icon_css = 'fa-user'
    class_views = ['profile', 'edit_account', 'edit_preferences',
                   'edit_password', 'edit_groups']


    # Fields
    firstname = Firstname_Field()
    lastname = Lastname_Field()
    email = UserEmail_Field()
    password = UserPassword_Field()
    avatar = File_Field(title=MSG('Avatar'))
    user_language = Char_Field()
    user_timezone = Char_Field()
    user_state = UserState_Field()
    groups = UserGroups_Field()
    username = Char_Field(indexed=True, stored=True, encrypted=True, datatype=String)

    # Remove some fields
    title = None
    description = None
    subject = None
    text = None


    ########################################################################
    # Indexing
    ########################################################################
    def get_catalog_values(self):
        values = super().get_catalog_values()
        # email domain
        email = self.get_value('email')
        if email and '@' in email:
            values['email_domain'] = email.split('@', 1)[1]
        # username (overrides default)
        values['username'] = self.get_login_name()
        # groups
        values['groups'] = self.get_value('groups')
        # Ok
        return values


    ########################################################################
    # API / Authentication
    ########################################################################
    def get_user_id(self):
        # Used by itools.web
        return str(self.name)


    def get_password(self):
        password = self.get_property('password')
        return password[-1] if password else None


    def get_auth_token(self):
        # Used by itools.web
        password = self.get_password()
        return password.value if password else None


    def authenticate(self, password):
        my_password = self.get_password()
        if my_password is None:
            return False
        algo = my_password.get_parameter('algo', 'sha1')
        salt = my_password.get_parameter('salt', '')

        password_hashed, salt = get_secure_hash(password, algo, salt)
        return password_hashed == my_password.value


    def _login(self, password, context):
        # We call this method '_login' to avoid a name clash with the login
        # view.

        if not self.authenticate(password):
            error = MSG_LOGIN_WRONG_NAME_OR_PASSWORD
        elif self.get_value('user_state') == 'inactive':
            error = ERROR(
                'Your account has been canceled, contact the administrator '
                ' if you want to get access again.')
        else:
            error = None
            context.login(self)

        # To activate this feature set the lastlog field
        lastlog = self.get_field('lastlog')
        if lastlog:
            success = error is None
            self.set_value('lastlog', context.timestamp, success=success)

        # Ok
        return error


    def update_pending_key(self):
        state = self.get_property('user_state')
        if state.value == 'pending':
            # TODO Implement expiration
            return state.get_parameter('key')

        key = generate_password(30)
        self.set_value('user_state', 'pending', key=key)
        return key


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
                return f'{firstname} {lastname}'
            return firstname
        if lastname:
            return lastname
        return self.get_login_name()


    login_name_property = 'email'
    def get_login_name(self):
        return self.get_value(self.login_name_property)


    def get_timezone(self):
        return self.get_value('user_timezone')


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
                           title=MSG('Edit groups'))



###########################################################################
# Users
###########################################################################
class Users(Folder):

    class_id = 'users'
    class_title = MSG('Users')
    class_description = MSG('Manage users.')
    class_icon_css = 'fa-user'
    class_views = ['browse_users', 'add_user', 'edit']

    # Configuration
    config_name = '/users'
    config_group = 'access'


    def get_document_types(self):
        return [self.database.get_resource_class('user')]


    # Views
    browse_users = Users_Browse()
    add_user = Users_AddUser()



###########################################################################
# Register
###########################################################################
register_field('email_domain', String(indexed=True, stored=True))
Configuration.register_module(Users)
