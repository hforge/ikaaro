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
from itools.core import freeze, thingy_property
from itools.datatypes import Enumerate, Tokens, Email, MultiLinesTokens
from itools.gettext import MSG
from itools.web import INFO, ERROR

# Import from ikaaro
from access import RoleAware_BrowseUsers
from autoform import AutoForm, TextWidget, ReadOnlyWidget, MultilineWidget
from buttons import Button, BrowseButton
from views import CompositeForm


MSG_USER_SUBSCRIBED = INFO(u'You are now subscribed to this resource.')
MSG_USER_UNSUBSCRIBED = INFO(u'You are now unsubscribed from this resource.')
MSG_SUBSCRIBED = INFO(u'The following users were subscribed: {users}.',
        format='replace_html')
MSG_UNSUBSCRIBED = INFO(u'The following users were unsubscribed: {users}.',
        format='replace_html')
MSG_ADDED = INFO(u'The following users were added: {users}.',
        format='replace_html')
MSG_UNALLOWED = ERROR(u'The following users are prevented from subscribing: '
        u'{users}.', format='replace_html')


def get_subscribed_message(message, users, context):
    pattern = u'<a href="{0}">{1}</a>'
    users = [pattern.format(context.get_link(user), user.get_title())
            for user in users]
    return message(users=", ".join(users))



class UsersList(Enumerate):

    included_roles = None

    def get_options(self):
        site_root = self.resource.get_site_root()

        # Members
        included_roles = self.included_roles
        if included_roles:
            members = set()
            for rolename in site_root.get_role_names():
                if rolename in included_roles:
                    usernames = site_root.get_property(rolename)
                    members.update(usernames)
        else:
            members = site_root.get_members()

        # Root admins are inherited (TODO Remove once we change this)
        if not included_roles or 'root-admins' in included_roles:
            root_admins = self.resource.get_root().get_property('admins')
            members.update(root_admins)

        users = site_root.get_resource('/users')
        options = []
        for name in members:
            user = users.get_resource(name, soft=True)
            if user is None:
                continue
            value = user.get_title()
            options.append({'name': name, 'value': value})

        options.sort(key=itemgetter('value'))
        return options



class UsersRawList(Tokens):

    @staticmethod
    def is_valid(value):
        if not value:
            return True
        for email in value:
            if not Email.is_valid(email):
                return False
        return True



class RegisterButton(Button):
    access = True
    name = 'register'
    title = MSG(u'Subscribe')


    @thingy_property
    def show(cls):
        if cls.context.user:
            if cls.resource.is_subscribed(cls.context.user.name):
                return False
        return super(RegisterButton, cls).show



class UnregisterButton(RegisterButton):
    name = 'unregister'
    title = MSG(u'Unsubscribe')


    @thingy_property
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
                return context.user.get_property('email')
            return context.query['email']
        proxy = super(RegisterForm, self)
        return proxy.get_value(self, resource, context, name, datatype)


    def action_register(self, resource, context, form):
        root = context.root
        email = form['email']
        existing_user = root.get_user_from_login(email)
        user = resource.subscribe_user(email=email, user=existing_user)

        if existing_user is None:
            # New user must confirm
            user.send_confirmation(context, email)
        else:
            if context.user is None:
                # Someone subscribed an existing user, warn him
                user.send_registration(context, email)
                # Else user subscribed himself, do nothing

        resource.after_register(user.name)

        context.message = MSG_USER_SUBSCRIBED


    def action_unregister(self, resource, context, form):
        root = context.root
        email = form['email']
        user = root.get_user_from_login(email)
        if user is not None:
            username = user.name
            resource.unsubscribe_user(username)
            resource.after_unregister(username)

        context.message = MSG_USER_UNSUBSCRIBED



class SubscribeButton(BrowseButton):
    access = True
    name = 'subscribe'
    title = MSG(u"Subscribe")



class UnsubscribeButton(SubscribeButton):
    name = 'unsubscribe'
    title = MSG(u"Unsubscribe")



class ManageForm(RoleAware_BrowseUsers):
    access = 'is_admin'
    title = MSG(u"Manage Subscriptions")
    description = None

    table_columns = freeze(RoleAware_BrowseUsers.table_columns +
            [('subscribed', MSG(u"Subscribed"))])
    table_actions = freeze([SubscribeButton, UnsubscribeButton])


    def get_items(self, resource, context):
        site_root = resource.get_site_root()
        return super(ManageForm, self).get_items(site_root, context)


    def get_item_value(self, resource, context, item, column):
        if column == 'subscribed':
            subscribed = item.name in resource.get_property('cc_list')
            return MSG(u"Yes") if subscribed else MSG(u"No")
        proxy = super(ManageForm, self)
        site_root = resource.get_site_root()
        return proxy.get_item_value(site_root, context, item, column)


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

        message = []
        if subscribed:
            message.append(get_subscribed_message(MSG_SUBSCRIBED, subscribed,
                context))
        if unallowed:
            message.append(get_subscribed_message(MSG_UNALLOWED, unallowed,
                context))
        context.message = message


    def action_unsubscribe(self, resource, context, form):
        users = context.root.get_resource('users')

        unsubscribed = []
        for username in form['ids']:
            user = users.get_resource(username)
            resource.unsubscribe_user(username)
            unsubscribed.append(user)

        context.message = get_subscribed_message(MSG_UNSUBSCRIBED,
                unsubscribed, context)



class MassSubscribeButton(Button):
    access = True
    name = 'mass_subscribe'
    title = MSG(u'OK')



class MassSubscriptionForm(AutoForm):
    access = 'is_admin'
    title = MSG(u"Mass Subscription")
    schema = freeze({'emails': MultiLinesTokens(mandatory=True)})
    widgets = freeze([MultilineWidget('emails', focus=False,
        title=MSG(u"E-mail addresses to subscribe"))])
    actions = [MassSubscribeButton, Button] # len(actions) > 1


    def get_value(self, resource, context, name, datatype):
        if name == 'emails':
            return ''
        proxy = super(MassSubscriptionForm, self)
        return proxy.get_value(resource, context, name, datatype)


    def action_mass_subscribe(self, resource, context, form):
        root = context.root
        site_root = resource.get_site_root()

        added = []
        subscribed = []
        unallowed = []
        for email in form['emails']:
            email = email.strip()
            if not email:
                continue
            existing_user = root.get_user_from_login(email)
            if existing_user is None:
                existing_role = None
            else:
                if not resource.is_subscription_allowed(existing_user.name):
                    unallowed.append(existing_user)
                    continue
                existing_role = site_root.get_user_role(existing_user.name)
            user = resource.subscribe_user(email=email, user=existing_user)
            if existing_user is None:
                # New user must confirm
                user.send_confirmation(context, email)
                added.append(user)
            else:
                if existing_role is None:
                    # User added to the website, inform him
                    user.send_registration(context, email)
                    # Else user already a member of the website
                subscribed.append(user)

        message = []
        if added:
            message.append(get_subscribed_message(MSG_ADDED, added, context))
        if subscribed:
            message.append(get_subscribed_message(MSG_SUBSCRIBED, subscribed,
                context))
        if unallowed:
            message.append(get_subscribed_message(MSG_UNALLOWED, unallowed,
                context))
        context.message = message



class SubscribeForm(CompositeForm):
    access = 'is_allowed_to_view'
    title = MSG(u'Subscriptions')

    subviews = [RegisterForm(), ManageForm(), MassSubscriptionForm()]



class Observable(object):

    class_schema = {'cc_list': Tokens(source='metadata')}


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


    def is_subscribed(self, username):
        return username in self.get_property('cc_list')


    def is_subscription_allowed(self, username):
        return True


    def subscribe_user(self, email=None, user=None):
        root = self.get_root()
        site_root = self.get_site_root()

        # Get the user
        if user is None:
            if email is None:
                raise ValueError, "email or user are mandatory"
            user = root.get_user_from_login(email)

        # Create it if needed
        if user is None:
            # Add the user
            users = root.get_resource('users')
            user = users.set_user(email, password=None)
            user_id = user.name
        else:
            user_id = user.name

        # Set the role
        if user_id not in site_root.get_members():
            site_root.set_user_role(user_id, role='guests')

        # Add to subscribers list
        cc_list = set(self.get_property('cc_list'))
        cc_list.add(user_id)
        self.set_property('cc_list', tuple(cc_list))

        return user


    def unsubscribe_user(self, username):
        cc_list = set(self.get_property('cc_list'))
        try:
            cc_list.remove(username)
        except KeyError:
            pass
        self.set_property('cc_list', tuple(cc_list))


    def after_register(self, username):
        pass


    def after_unregister(self, username):
        pass


    def notify_subscribers(self, context):
        # 1. Check the resource has been modified
        if not context.database.is_changed(self):
            return

        # 2. Get list of subscribed users
        users = self.metadata.get_property('cc_list')
        if not users:
            return

        # 3. Build the message for each language
        site_root = self.get_site_root()
        website_languages = site_root.get_property('website_languages')
        default_language = site_root.get_default_language()
        messages_dict = {}
        for language in website_languages:
            messages_dict[language] = self.get_message(context,
                                                       language=language)

        # 4. Send the message
        for user in users.value:
            user = context.root.get_user(user)
            if user and not user.get_property('user_must_confirm'):
                mail = user.get_property('email')

                language = user.get_property('user_language')
                if language not in website_languages:
                    language = default_language
                subject, body = messages_dict[language]

                context.root.send_email(mail, subject, text=body)


    #######################################################################
    # UI
    #######################################################################

    subscribe = SubscribeForm()
