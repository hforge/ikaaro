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
from itools.datatypes import Enumerate
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



class SubscribeForm(STLForm):

    access = 'is_allowed_to_view'
    title = MSG(u'Subscriptions')
    template = '/ui/subscribe.xml'

    def get_schema(self, resource, context):
        return {'cc_list': UsersList(resource=resource, multiple=True)}


    def get_namespace(self, resource, context):
        cc = resource.get_property('cc_list')

        # Admin
        ac = resource.get_access_control()
        is_admin = ac.is_admin(context.user, resource)

        # Current user
        user = context.user
        if user:
            username = user.name
            user_title = user.get_title()
            user_checked = username in cc
        else:
            username = user_title = user_checked = None

        # Other users
        root = context.root
        site_root = resource.get_site_root()
        subscribed = []
        not_subscribed = []
        for name in site_root.get_members():
            if name == username:
                continue
            user = {'name': name, 'title': root.get_user_title(name)}
            if name in cc:
                subscribed.append(user)
            else:
                not_subscribed.append(user)
        subscribed.sort(key=itemgetter('title'))
        not_subscribed.sort(key=itemgetter('title'))

        # Ok
        return {
            'is_admin': is_admin,
            'user_name': username,
            'user_title': user_title,
            'user_checked': user_checked,
            'subscribed': subscribed,
            'not_subscribed': not_subscribed}


    def action(self, resource, context, form):
        new_cc = form.get('cc_list')

        # Case 1: anonymous user, not yet supported
        user = context.user
        if user is None:
            context.message = ERROR(u'Anonymous users not yet supported.')
            return

        # Case 2: admin
        ac = resource.get_access_control()
        is_admin = ac.is_admin(context.user, resource)
        if is_admin:
            resource.set_property('cc_list', tuple(new_cc))
            context.message = MSG_CHANGES_SAVED
            return

        # Case 3: someone else
        old_cc = resource.get_property('cc_list')
        if user.name in new_cc:
            new_cc = list(old_cc)
            new_cc.append(user.name)
        else:
            new_cc = list(old_cc)
            new_cc.remove(user.name)

        resource.set_property('cc_list', tuple(new_cc))
        context.message = MSG_CHANGES_SAVED



class Observable(object):


    def notify_subscribers(self, context):
        # Subject
        subject = MSG(u'[{title}] has been modified')
        subject = subject.gettext(title=self.get_title())
        # Body
        message = MSG(u'DO NOT REPLY TO THIS EMAIL. To view modifications '
                u'please visit:\n{resource_uri}')
        uri = str(context.uri)
        uri = uri.split(';')[0] + ';commit_log'
        body = message.gettext(resource_uri=uri)

        # get list of registered users
        users = self.metadata.get_property('cc_list')
        # cc_list is empty
        if not users:
            return
        # Notify registered users
        for user in users.value:
            user = context.root.get_user(user)
            if not user:
                continue
            mail = user.get_property('email')
            context.root.send_email(mail, subject, text=body)


    #######################################################################
    # UI
    #######################################################################

    subscribe = SubscribeForm()
