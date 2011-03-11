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
from itools.datatypes import Enumerate, Tokens, Email, Boolean
from itools.gettext import MSG
from itools.web import STLForm, ERROR

# Import from ikaaro
from messages import MSG_CHANGES_SAVED



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



class SubscribeForm(STLForm):

    access = 'is_allowed_to_view'
    title = MSG(u'Subscriptions')
    template = '/ui/subscribe.xml'


    def get_schema(self, resource, context):
        return {'x_email': Email(mandatory=context.user is None),
                'x_subscribe': Boolean(default=True),
                'cc_list': UsersList(resource=resource, multiple=True),
                'new_users': UsersRawList()}


    def get_namespace(self, resource, context):
        namespace = super(SubscribeForm, self).get_namespace(resource, context)

        # Anomymous
        x_subscribe = namespace['x_subscribe']['value'] == '1'
        namespace['x_subscribe']['0_is_checked'] = not x_subscribe
        namespace['x_subscribe']['1_is_checked'] = x_subscribe

        # Get the good cc_list
        submit = (context.method == 'POST')
        if submit:
            cc_list = context.get_form_value('cc_list',
                      type=UsersList(resource=resource, multiple=True))
        else:
            cc_list = resource.get_property('cc_list')

        # Admin
        ac = resource.get_access_control()
        is_admin = ac.is_admin(context.user, resource)

        # Current user
        current_user = None
        user = context.user
        if user:
            # Find the user
            for a_user in namespace['cc_list']['value']:
                if a_user['name'] == user.name:
                    current_user = a_user
                    current_user['selected'] = user.name in cc_list
                    break

        # Other users
        subscribed = []
        not_subscribed = []
        for a_user in namespace['cc_list']['value']:
            if user and a_user['name'] == user.name:
                continue
            if a_user['name'] in cc_list:
                a_user['selected'] = True
                subscribed.append(a_user)
            else:
                a_user['selected'] = False
                not_subscribed.append(a_user)
        subscribed.sort(key=itemgetter('value'))
        not_subscribed.sort(key=itemgetter('value'))

        # Ok
        return {'x_email': namespace['x_email'],
                'x_subscribe': namespace['x_subscribe'],
                'current_user': current_user,
                'is_admin': is_admin,
                'subscribed': subscribed,
                'not_subscribed': not_subscribed,
                'new_users': namespace['new_users']}


    def _add_user(self, resource, context, email):
        root = context.root
        site_root = resource.get_site_root()
        users = root.get_resource('users')

        # Get the user
        user = root.get_user_from_login(email)

        # Get the user (create it if needed)
        if user is None:
            # Add the user
            user = users.set_user(email, password=None)
            user_id = user.name
            user.send_confirmation(context, email)
        else:
            user_id = user.name
            # Check the user is not yet in the group
            if user_id in site_root.get_members():
                return user_id
            user.send_registration(context, email)

        # Set the role
        site_root.set_user_role(user_id, role='guests')
        return user_id


    def _reset_context(self, resource, context, new_cc):
        resource.set_property('cc_list', tuple(new_cc))
        context.get_form()['x_email'] = ''
        context.get_form()['x_subscribe'] = True
        context.get_form()['cc_list'] = list(new_cc)
        context.get_form()['new_users'] = ''


    def action(self, resource, context, form):
        x_email = form.get('x_email')
        x_subscribe = form.get('x_subscribe')
        new_cc = form.get('cc_list')
        new_users = form.get('new_users')

        # Case 1: anonymous user
        user = context.user
        if user is None:
            new_cc = set(resource.get_property('cc_list'))

            if x_subscribe:
                new_id = self._add_user(resource, context, x_email)
                new_cc.add(new_id)
                context.message = MSG(
 u'A new account has been created and you are now registered to this resource')
            else:
                # Check whether the user already exists
                user = context.root.get_user_from_login(x_email)
                if user:
                    new_cc.discard(user.name)
                    context.message = MSG_CHANGES_SAVED
                else:
                    context.message = ERROR(
                                    u'This user was not in our database')
            # Ok
            resource.set_property('cc_list', tuple(new_cc))
            context.get_form()['cc_list'] = list(new_cc)
            context.get_form()['new_users'] = ''
            return

        # Case 2: admin
        ac = resource.get_access_control()
        is_admin = ac.is_admin(context.user, resource)
        if is_admin:
            new_id_set = set()
            for email in new_users:
                new_id_set.add(self._add_user(resource, context, email))
            new_cc = set(new_cc).union(new_id_set)

            # Ok
            context.message = MSG_CHANGES_SAVED
            self._reset_context(resource, context, new_cc)
            return

        # Case 3: someone else
        old_cc = resource.get_property('cc_list')
        if user.name in new_cc:
            new_cc = set(old_cc)
            new_cc.add(user.name)
        else:
            new_cc = set(old_cc)
            new_cc.discard(user.name)

        # Ok
        context.message = MSG_CHANGES_SAVED
        self._reset_context(resource, context, new_cc)



class Observable(object):

    class_schema = {'cc_list': Tokens(source='metadata')}


    def notify_subscribers(self, context):
        # 1. Check the resource has been modified
        if not context.database.is_changed(self):
            return

        # 2. Get list of subscribed users
        users = self.metadata.get_property('cc_list')
        if not users:
            return

        # 3. Build the message
        # Subject
        subject = MSG(u'[{title}] has been modified')
        subject = subject.gettext(title=self.get_title())
        # Body
        message = MSG(u'DO NOT REPLY TO THIS EMAIL. To view modifications '
                u'please visit:\n{resource_uri}')
        uri = str(context.uri)
        uri = uri.split(';')[0] + ';commit_log'
        body = message.gettext(resource_uri=uri)

        # 4. Send the message
        for user in users.value:
            user = context.root.get_user(user)
            if user and not user.get_property('user_must_confirm'):
                mail = user.get_property('email')
                context.root.send_email(mail, subject, text=body)


    #######################################################################
    # UI
    #######################################################################

    subscribe = SubscribeForm()
