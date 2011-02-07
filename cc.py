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
from itools.datatypes import Enumerate, Tokens, Email
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
        if not included_roles or 'admins' in included_roles:
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
        return {'cc_list': UsersList(resource=resource, multiple=True),
                'new_users': UsersRawList()}


    def get_namespace(self, resource, context):
        namespace = super(SubscribeForm, self).get_namespace(resource, context)

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
        user = context.user
        if user:
            # Find the user
            for an_user in namespace['cc_list']['value']:
                if an_user['name'] == user.name:
                    current_user = an_user
                    current_user['selected'] = user.name in cc_list
                    break
        else:
            current_user = None

        # Other users
        subscribed = []
        not_subscribed = []
        for an_user in namespace['cc_list']['value']:
            if user and an_user['name'] == user.name:
                continue
            if an_user['name'] in cc_list:
                an_user['selected'] = True
                subscribed.append(an_user)
            else:
                an_user['selected'] = False
                not_subscribed.append(an_user)
        subscribed.sort(key=itemgetter('value'))
        not_subscribed.sort(key=itemgetter('value'))

        # Ok
        return {'current_user': current_user,
                'is_admin': is_admin,
                'subscribed': subscribed,
                'not_subscribed': not_subscribed,
                'new_users': namespace['new_users']}


    def _add_user(self, resource, context, email):
        root = context.root
        site_root = resource.get_site_root()
        users = root.get_resource('users')

        # Check whether the user already exists
        results = root.search(email=email)
        if len(results):
            user_id = results.get_documents()[0].name
        else:
            user_id = None

        # Get the user (create it if needed)
        if user_id is None:
            # Add the user
            user = users.set_user(email, password=None)
            user_id = user.name
            user.send_confirmation(context, email)
        else:
            # Check the user is not yet in the group
            if user_id in site_root.get_members():
                return user_id
            user = users.get_resource(user_id)
            user.send_registration(context, email)

        # Set the role
        site_root.set_user_role(user_id, role='guests')
        return user_id


    def action(self, resource, context, form):
        new_cc = form.get('cc_list')
        new_users = form.get('new_users')

        # Case 1: anonymous user, not yet supported
        user = context.user
        if user is None:
            context.message = ERROR(u'Anonymous users not yet supported.')
            return

        # Case 2: admin
        ac = resource.get_access_control()
        is_admin = ac.is_admin(context.user, resource)
        if is_admin:
            new_id_set = set()
            for email in new_users:
                new_id_set.add(self._add_user(resource, context, email))
            new_cc = set(new_cc).union(new_id_set)
            resource.set_property('cc_list', tuple(new_cc))
            context.message = MSG_CHANGES_SAVED
            context.get_form()['cc_list'] = list(new_cc)
            context.get_form()['new_users'] = ''
            return

        # Case 3: someone else
        old_cc = resource.get_property('cc_list')
        if user.name in new_cc:
            new_cc = set(old_cc)
            new_cc.add(user.name)
        else:
            new_cc = set(old_cc)
            new_cc.discard(user.name)
        resource.set_property('cc_list', tuple(new_cc))
        context.message = MSG_CHANGES_SAVED
        context.get_form()['cc_list'] = list(new_cc)
        context.get_form()['new_users'] = ''



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
            if user:
                mail = user.get_property('email')
                context.root.send_email(mail, subject, text=body)


    #######################################################################
    # UI
    #######################################################################

    subscribe = SubscribeForm()
