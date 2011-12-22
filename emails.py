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
from itools.core import prototype
from itools.gettext import MSG


###########################################################################
# Base classes
###########################################################################
class Email(prototype):

    subject = None
    text = None


    def get_text_namespace(self, context):
        host_uri = str(context.uri.resolve('/'))[:-1]
        namespace = {
            'host': host_uri,
            'host_title': context.root.get_title()}

        return namespace


    def get_text(self, context):
        namespace = self.get_text_namespace(context)
        return self.text.gettext(**namespace)



# Registry
emails_registry = {}


# Public API
def register_email(cls):
    emails_registry[cls.class_id] = cls


def send_email(email_id, context, to_addr, **kw):
    email = emails_registry.get(email_id)
    if email:
        email = email(**kw)
        text = email.get_text(context)
        context.root.send_email(to_addr, email.subject, text=text)



###########################################################################
# User email
###########################################################################
class User_Email(Email):

    user = None
    def get_text_namespace(self, context):
        namespace = super(User_Email, self).get_text_namespace(context)
        # User specific information
        user = self.user
        if user:
            namespace['user'] = namespace['host'] + str(user.abspath)
            namespace['userid'] = user.get_login_name()
            user_state = user.get_property('user_state')
            namespace['userkey'] = user_state.get_parameter('key')

        return namespace


class User_AskForConfirmation(User_Email):
    """This email asks the user to confirm his subscription to the web site.
    It is send in two conditions:

    - When he registers through the registration form
    - When the administrator registers him through the back-office
    """

    class_id = 'user-ask-for-confirmation'
    subject = MSG(u'Registration confirmation')
    text = MSG(
        u'To confirm your identity, follow this link:\n'
        u'\n'
        u' {user}/;confirm_registration?username={userid}&key={userkey}')



class AddUser_SendNotification(User_Email):

    class_id = 'add-user-send-notification'
    subject = MSG(u'Registration notification')
    text = MSG(
        u'You have been registered to the "{host_title}" site:\n'
        u'\n'
        u' {host}/')



class Register_AlreadyRegistered(User_Email):

    class_id = 'register-already-registered'
    subject = MSG(u"Already registered")
    text = MSG(
        u'You already have an account:\n'
        u'\n'
        u' {host}/;login?loginname={userid}')



class Register_SendConfirmation(User_Email):

    class_id = 'register-send-confirmation'
    subject = MSG(u"Registration confirmed")
    text = MSG(
        u'You have been registered to the "{host_title}" site:\n'
        u'\n'
        u' {host}/')



class ForgottenPassword_AskForConfirmation(User_Email):

    class_id = 'forgotten-password-ask-for-confirmation'
    subject = MSG(u"Choose a new password")
    text = MSG(
        u'To choose a new password, click the link:\n'
        u'\n'
        u' {user}/;change_password_forgotten?username={userid}&key={userkey}')


class SwitchState_Activate(User_Email):

    class_id = 'switch-state-activate'
    subject = MSG(u'Your account has been re-activated')
    text = MSG(u'Your account has been re-activated')


class SwitchState_Deactivate(User_Email):

    class_id = 'switch-state-deactivate'
    subject = MSG(u'Your account has been canceled')
    text = MSG(u'Your account has been canceled')


# Registry
register_email(User_AskForConfirmation)
register_email(AddUser_SendNotification)
register_email(Register_AlreadyRegistered)
#register_email(Register_SendConfirmation)
register_email(ForgottenPassword_AskForConfirmation)
register_email(SwitchState_Activate)
register_email(SwitchState_Deactivate)
