# -*- coding: UTF-8 -*-
# Copyright (C) 2010 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from operator import itemgetter

# Import from itools
from itools.core import freeze, proto_property
from itools.csv import Property
from itools.database import Resource
from itools.datatypes import Email, Enumerate, MultiLinesTokens
from itools.datatypes import String
from itools.gettext import MSG
from itools.web import get_context, INFO, ERROR

# Import from ikaaro
from autoform import AutoForm, TextWidget, ReadOnlyWidget, MultilineWidget
from autoform import HiddenWidget
from buttons import Button, BrowseButton
from fields import Select_Field
from messages import MSG_BAD_KEY
from users_views import BrowseUsers
from utils import generate_password
from views import CompositeView


MSG_CONFIRMATION_SENT = INFO(u'A message has been sent to confirm your '
        u'identity.')
MSG_USER_SUBSCRIBED = INFO(u'You are now subscribed.')
MSG_USER_ALREADY_SUBSCRIBED = ERROR(u'You were already subscribed.')
MSG_USER_UNSUBSCRIBED = INFO(u'You are now unsubscribed.')
MSG_USER_ALREADY_UNSUBSCRIBED = ERROR(u'You were already unsubscribed.')
MSG_ALREADY = INFO(u'The following users are already subscribed: {users}.',
        format='replace_html')
MSG_SUBSCRIBED = INFO(u'The following users were subscribed: {users}.',
        format='replace_html')
MSG_UNSUBSCRIBED = INFO(u'The following users were unsubscribed: {users}.',
        format='replace_html')
MSG_INVALID = ERROR(u'The following addresses are invalid: {users}.',
        format='replace_html')
MSG_INVITED = INFO(u'The following users have been invited: {users}.',
        format='replace_html')
MSG_UNALLOWED = ERROR(u'The following users are prevented from subscribing: '
        u'{users}.', format='replace_html')


def add_subscribed_message(message, users, context, users_is_resources=True):
    if users:
        if users_is_resources is True:
            format = u'<a href="{0}">{1}</a>'.format
            users = [ format(context.get_link(x), x.get_title())
                        for x in users ]
        users = ', '.join(users)
        message = message(users=users)
        context.message.append(message)



class RegisterButton(Button):
    access = True
    name = 'register'
    title = MSG(u'Subscribe')


    @proto_property
    def show(cls):
        if cls.context.user:
            if cls.resource.is_subscribed(cls.context.user.name):
                return False
        return super(RegisterButton, cls).show



class UnregisterButton(RegisterButton):
    name = 'unregister'
    title = MSG(u'Unsubscribe')


    @proto_property
    def show(cls):
        if cls.context.user:
            if not cls.resource.is_subscribed(cls.context.user.name):
                return False
        return super(RegisterButton, cls).show



class RegisterForm(AutoForm):
    access = 'is_allowed_to_view'
    title = MSG(u"Subscription")
    schema = freeze({'email': Email(mandatory=True)})
    widgets = freeze([TextWidget('email', title=MSG(u"E-mail Address"))])
    query_schema = freeze({
        'email': Email})
    actions = [RegisterButton, UnregisterButton]

    # Messages
    msg_user_already_subscribed = MSG_USER_ALREADY_SUBSCRIBED
    msg_confirmation_sent = MSG_CONFIRMATION_SENT
    msg_user_subscribed = MSG_USER_SUBSCRIBED
    msg_user_already_unsubscribed = MSG_USER_ALREADY_UNSUBSCRIBED
    msg_user_unsubscribed = MSG_USER_UNSUBSCRIBED


    def get_widgets(self, resource, context):
        widgets = super(RegisterForm, self).get_widgets(resource, context)
        if context.user:
            # E-mail becomes hard coded
            widgets = list(widgets)
            email = widgets[0]
            widgets[0] = ReadOnlyWidget(name=email.name, focus=True,
                    title=email.title)
        return widgets


    def get_value(self, resource, context, name, datatype):
        if name == 'email':
            if context.user:
                return context.user.get_value('email')
            return context.query['email']
        proxy = super(RegisterForm, self)
        return proxy.get_value(self, resource, context, name, datatype)


    def action_register(self, resource, context, form):
        root = context.root
        email = form['email']
        existing_user = root.get_user_from_login(email)

        if existing_user is not None:
            username = existing_user.name
            if resource.is_subscribed(username, skip_unconfirmed=False):
                context.message = self.msg_user_already_subscribed
                return

        # Create user anyhow
        user = resource.subscribe_user(email=email, user=existing_user)

        if context.user is None:
            # Anonymous subscription
            resource.send_confirm_register(user, context)
            context.message = self.msg_confirmation_sent
        else:
            resource.after_register(user.name)
            context.message = self.msg_user_subscribed


    def action_unregister(self, resource, context, form):
        user = context.root.get_user_from_login(form['email'])
        if user is None:
            context.message = self.msg_user_already_unsubscribed
            return

        username = user.name
        if not resource.is_subscribed(username, skip_unconfirmed=False):
            context.message = self.msg_user_already_unsubscribed
            return

        if context.user is None:
            # Anonymous subscription
            resource.send_confirm_register(user, context, unregister=True)
            context.message = self.msg_confirmation_sent
        else:
            resource.unsubscribe_user(username)
            resource.after_unregister(username)
            context.message = self.msg_user_unsubscribed



class SubscribeButton(BrowseButton):
    access = True
    name = 'subscribe'
    title = MSG(u"Subscribe")



class UnsubscribeButton(SubscribeButton):
    name = 'unsubscribe'
    title = MSG(u"Unsubscribe")



class ManageForm(BrowseUsers):
    access = 'is_admin'
    title = MSG(u"Manage Subscriptions")
    description = None

    table_columns = freeze(
            [('checkbox', None)]
            + BrowseUsers.table_columns[2:-2]
            + [('state', MSG(u'State'))])
    table_actions = freeze([SubscribeButton, UnsubscribeButton])


    def get_items(self, resource, context):
        return super(ManageForm, self).get_items(context.root, context)


    def get_item_value(self, resource, context, item, column):
        if column == 'state':
            for cc in resource.get_property('cc_list'):
                if item.name == cc.value:
                    status = cc.get_parameter('status')
                    if status == 'S':
                        return MSG(u'Pending confirmation')
                    return MSG(u'Subscribed')

            return MSG(u'Not subscribed')

        proxy = super(ManageForm, self)
        return proxy.get_item_value(context.root, context, item, column)


    def action_subscribe(self, resource, context, form):
        users = context.root.get_resource('users')

        subscribed = []
        unallowed = []
        for username in form['ids']:
            user = users.get_resource(username)
            if not resource.is_subscription_allowed(username):
                unallowed.append(user)
                continue
            resource.subscribe_user(user=user)
            subscribed.append(user)

        context.message = []
        add_subscribed_message(MSG_SUBSCRIBED, subscribed, context)
        add_subscribed_message(MSG_UNALLOWED, unallowed, context)


    def action_unsubscribe(self, resource, context, form):
        users = context.root.get_resource('users')

        unsubscribed = []
        for username in form['ids']:
            user = users.get_resource(username)
            resource.unsubscribe_user(username)
            unsubscribed.append(user)

        context.message = []
        add_subscribed_message(MSG_UNSUBSCRIBED, unsubscribed, context)



class MassSubscribeButton(Button):
    access = True
    name = 'mass_subscribe'
    title = MSG(u'OK')



class MassSubscriptionForm(AutoForm):

    access = 'is_admin'
    title = MSG(u"Mass Subscription")
    description = MSG(
        u"An invitation will be sent to every address typen below, one by"
        u" line.")
    schema = freeze({'emails': MultiLinesTokens(mandatory=True)})
    widgets = freeze([MultilineWidget('emails', focus=False,)])
    actions = [MassSubscribeButton, Button] # len(actions) > 1


    def get_value(self, resource, context, name, datatype):
        if name == 'emails':
            return ''
        proxy = super(MassSubscriptionForm, self)
        return proxy.get_value(resource, context, name, datatype)


    def action_mass_subscribe(self, resource, context, form):
        root = context.root

        already = []
        unallowed = []
        invited = []
        invalid = []
        subscribed_users = resource.get_subscribed_users()
        for email in form['emails']:
            email = email.strip()
            if not email:
                continue
            # Check if email is valid
            if not Email.is_valid(email):
                invalid.append(email)
                continue

            # Checks
            user = root.get_user_from_login(email)
            if user:
                if user.name in subscribed_users:
                    already.append(user)
                    continue
                if not resource.is_subscription_allowed(user.name):
                    unallowed.append(user)
                    continue

            # Subscribe
            user = resource.subscribe_user(email=email, user=user)
            key = resource.set_register_key(user.name)
            # Send invitation
            subject = resource.invitation_subject.gettext()
            confirm_url = context.uri.resolve(';accept_invitation')
            confirm_url.query = {'key': key, 'email': email}
            text = resource.invitation_text.gettext(uri=confirm_url)
            root.send_email(email, subject, text=text)
            invited.append(user)

        # Ok
        context.message = []
        add_subscribed_message(MSG_ALREADY, already, context)
        add_subscribed_message(MSG_INVALID, invalid, context,
                               users_is_resources=False)
        add_subscribed_message(MSG_INVITED, invited, context)
        add_subscribed_message(MSG_UNALLOWED, unallowed, context)



class SubscribeForm(CompositeView):
    access = 'is_allowed_to_view'
    title = MSG(u'Subscriptions')

    subviews = [RegisterForm, ManageForm, MassSubscriptionForm]



class ConfirmSubscription(AutoForm):

    access = 'is_allowed_to_view'
    title = MSG(u"Subscribe")
    description = MSG(
        u'By confirming your subscription to this resource you will'
        u' receive an email every time this resource is modified.')

    schema = freeze({
        'key': String(mandatory=True),
        'email': Email(mandatory=True)})
    widgets = freeze([
        HiddenWidget('key'),
        ReadOnlyWidget('email')])
    actions = [
        Button(access=True, title=MSG(u'Confirm subscription'))]

    key_status = 'S'
    msg_already = MSG_USER_ALREADY_SUBSCRIBED


    def get_value(self, resource, context, name, datatype):
        if name in ('key', 'email'):
            return context.get_query_value(name)
        proxy = super(ConfirmSubscription, self)
        return proxy.get_value(resource, context, name, datatype)


    def get_username(self, resource, context, key):
        # 1. Get the user
        email = context.get_form_value('email')
        user = context.root.get_user_from_login(email)
        if user is None:
            return None, MSG(u'Bad email')

        # 2. Get the user key
        username = user.name
        user_key = resource.get_register_key(username, self.key_status)
        if user_key is None:
            return username, self.msg_already

        # 3. Check the key
        if user_key != key:
            return username, MSG_BAD_KEY

        # 4. Ok
        return username, None


    def get_namespace(self, resource, context):
        key = context.get_form_value('key')
        username, error = self.get_username(resource, context, key)
        if error:
            return context.come_back(error, goto='./')

        proxy = super(ConfirmSubscription, self)
        return proxy.get_namespace(resource, context)


    def action(self, resource, context, form):
        username, error = self.get_username(resource, context, form['key'])
        if error:
            context.message = error
            return

        # Ok
        resource.reset_register_key(username)
        resource.after_register(username)
        return context.come_back(MSG_USER_SUBSCRIBED, goto='./')


class ConfirmUnsubscription(ConfirmSubscription):

    title = MSG(u'Unsubscribe')
    description = MSG(
        u'Confirm to stop receiving emails every time this resource is'
        u' modified.')

    actions = [
        Button(access=True, title=MSG(u'Confirm unsubscription'))]

    key_status = 'U'
    msg_already = MSG_USER_ALREADY_UNSUBSCRIBED


    def action(self, resource, context, form):
        username, error = self.get_username(resource, context, form['key'])
        if error:
            context.message = error
            return

        # Ok
        resource.unsubscribe_user(username)
        resource.after_unregister(username)
        return context.come_back(MSG_USER_UNSUBSCRIBED, goto='./')



class AcceptInvitation(ConfirmSubscription):

    title = MSG(u"Invitation")
    description = MSG(
        u'By accepting the invitation you will receive an email every time'
        u' this resource is modified.')
    actions = [
        Button(access=True, title=MSG(u'Accept invitation'))]



class Followers_Datatype(Enumerate):

    def get_options(self):
        root = get_context().root
        options = [
            {'name': user.name, 'value': user.get_title()}
            for user in root.get_resources('/users') ]

        options.sort(key=itemgetter('value'))
        return options



class Followers_Field(Select_Field):

    parameters_schema = {'status': String, 'key': String}
    datatype = Followers_Datatype
    has_empty_option = False



class Observable(Resource):

    # Fields
    cc_list = Followers_Field(multiple=True, indexed=True,
                              title=MSG(u'Followers'))

    confirm_register_subject = MSG(u"Confirmation required")
    confirm_register_text = MSG(
        u'To confirm subscription, click the link:\n\n {uri}\n')

    confirm_unregister_subject = MSG(u"Confirmation required")
    confirm_unregister_text = MSG(
        u'To confirm unsubscription, click the link:\n\n {uri}\n')

    invitation_subject = MSG(u'Invitation')
    invitation_text = MSG(
        u'To accept the invitation, click the link\n\n {uri}\n')


    def get_message(self, context, language=None):
        """This function must return the tuple (subject, body)
        """
        # Subject
        subject = MSG(u'[{title}] has been modified')
        subject = subject.gettext(title=self.get_title(), language=language)
        # Body
        message = MSG(u'DO NOT REPLY TO THIS EMAIL. To view modifications '
                      u'please visit:\n{resource_uri}')
        uri = context.get_link(self)
        uri = str(context.uri.resolve(uri))
        uri += '/;commit_log'
        body = message.gettext(resource_uri=uri, language=language)
        # And return
        return subject, body


    def get_subscribed_users(self, skip_unconfirmed=True):
        cc_list = self.get_property('cc_list')
        if not cc_list:
            return []

        users = []
        for cc in cc_list:
            # case 1: subscribed user or unsubscription pending user
            status = cc.get_parameter('status')
            if status in (None, 'U'):
                users.append(cc.value)
                continue

            # other
            if skip_unconfirmed is False and status == 'S':
                users.append(cc.value)

        return users


    def is_subscribed(self, username, skip_unconfirmed=True):
        return username in self.get_subscribed_users(skip_unconfirmed)


    def is_confirmed(self, username):
        for cc in self.get_property('cc_list'):
            if cc.value == username:
                status = cc.get_parameter('status')
                return status is None
        return False


    def is_subscription_allowed(self, username):
        return True


    def get_register_key(self, username, status='S'):
        for cc in self.get_property('cc_list'):
            if cc.value == username and cc.get_parameter('status') == status:
                return cc.get_parameter('key')
        return None


    def set_register_key(self, username, unregister=False):
        cc_list = self.get_property('cc_list')
        status = 'U' if unregister is True else 'S'
        # Find existing key
        for cc in cc_list:
            key = cc.get_parameter('key')
            if (cc.value == username and cc.get_parameter('status') == status
                and key is not None):
                # Reuse found key
                return key
        # Generate key
        key = generate_password(30)
        # Filter out username
        cc_list = [ cc for cc in cc_list if cc.value != username ]
        # Create new dict to force metadata commit
        cc_list.append(Property(username, status=status, key=key))
        self.set_property('cc_list', cc_list)
        return key


    def reset_register_key(self, username):
        cc_list = self.get_property('cc_list')
        # Filter out username
        cc_list = [ cc for cc in cc_list if cc.value != username ]
        # Create new dict to force metadata commit
        cc_list.append(Property(username))
        self.set_property('cc_list', cc_list)


    def subscribe_user(self, email=None, user=None):
        root = self.get_resource('/')

        # Get the user
        if user is None:
            if email is None:
                raise ValueError, "email or user are mandatory"
            user = root.get_user_from_login(email)

        # Create it if needed
        if user is None:
            user = root.make_user(email, password=None)
            # Mark it as new
            key = generate_password(30)
            user.set_property('user_state', 'pending', key=key)

        # Add to subscribers list
        self.reset_register_key(user.name)

        return user


    def unsubscribe_user(self, username):
        cc_list = self.get_property('cc_list')
        # Filter out username
        cc_list = [ cc for cc in cc_list if cc.value != username ]
        self.set_property('cc_list', cc_list)


    def after_register(self, username):
        pass


    def after_unregister(self, username):
        pass


    def send_confirm_register(self, user, context, unregister=False):
        username = user.name
        if unregister is False:
            key = self.set_register_key(username)
            view = ';confirm_register'
            subject = self.confirm_register_subject
            text = self.confirm_register_text
        else:
            key = self.set_register_key(username, unregister=True)
            view = ';confirm_unregister'
            subject = self.confirm_unregister_subject
            text = self.confirm_unregister_text

        # Build the confirmation link
        confirm_url = context.uri.resolve(view)
        email = user.get_value('email')
        confirm_url.query = {'key': key, 'email': email}
        subject = subject.gettext()
        text = text.gettext(uri=confirm_url)
        context.root.send_email(email, subject, text=text)


    def notify_subscribers(self, context):
        # 1. Check the resource has been modified
        # XXX This test is broken now comments are stored as separate objects
#       if not context.database.is_changed(self):
#           return

        # 2. Get list of subscribed users
        users = self.get_subscribed_users()
        if not users:
            return

        # 3. Build the message for each language
        root = context.root
        website_languages = root.get_value('website_languages')
        default_language = root.get_default_language()
        messages_dict = {}
        for language in website_languages:
            messages_dict[language] = self.get_message(context, language)

        # 4. Send the message
        auth_user = context.user.name if context.user else None

        for username in users:
            if username == auth_user:
                continue
            # Not confirmed yet
            if self.get_register_key(username) is not None:
                continue
            user = root.get_user(username)
            if user and user.get_value('user_state') == 'active':
                mail = user.get_value('email')

                language = user.get_value('user_language')
                if language not in website_languages:
                    language = default_language
                subject, body = messages_dict[language]

                root.send_email(mail, subject, text=body)


    #######################################################################
    # UI
    #######################################################################
    subscribe = SubscribeForm
    confirm_register = ConfirmSubscription
    confirm_unregister = ConfirmUnsubscription
    accept_invitation = AcceptInvitation
