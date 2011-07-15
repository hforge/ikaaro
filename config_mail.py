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

# Import from the Standard Library
from operator import itemgetter

# Import from itools
from itools.core import merge_dicts
from itools.datatypes import Enumerate, String, Tokens, Unicode
from itools.gettext import MSG

# Import from ikaaro
from autoedit import AutoEdit
from autoform import MultilineWidget, SelectWidget
from config import Configuration
from resource_ import DBResource



class ContactsOptions(Enumerate):

    @classmethod
    def get_options(cls):
        options = []
        resource = cls.resource
        users = resource.get_resource('/users')
        for user_name in resource.get_members():
            user = users.get_resource(user_name, soft=True)
            if user is None:
                continue
            user_title = user.get_title()
            user_email = user.get_property('email')
            if user_title != user_email:
                user_title = '%s <%s>' % (user_title, user_email)
            else:
                user_title = user_email
            options.append({'name': user_name, 'value': user_title,
                            'sort_value': user_title.lower()})
        options.sort(key=itemgetter('sort_value'))
        return options



mail_description = MSG(u'Configure the website email options')


class ConfigMail_Edit(AutoEdit):

    title = MSG(u'Email options')
    description = mail_description
    fields = ['emails_from_addr', 'emails_signature', 'contacts']

    def _get_schema(self, resource, context):
        schema = super(ConfigMail_Edit, self)._get_schema(resource, context)

        resource = resource.get_site_root()
        schema['emails_from_addr'] = ContactsOptions(resource=resource)
        schema['contacts'] = ContactsOptions(multiple=True, resource=resource)

        return schema


class SelectWidgetWithoutEmptyOption(SelectWidget):

    has_empty_option = False


class ConfigMail(DBResource):

    class_id = 'config-mail'
    class_title = MSG(u'Email options')
    class_description = mail_description
    class_icon48 = 'icons/48x48/mail.png'

    class_schema = merge_dicts(
        DBResource.class_schema,
        contacts=Tokens(
            source='metadata', title=MSG(u'Select the contact accounts'),
            widget=SelectWidgetWithoutEmptyOption),
        emails_from_addr=String(
            source='metadata', title=MSG(u'Emails from addr'),
            widget=SelectWidget),
        emails_signature=Unicode(
            source='metadata', title=MSG(u'Emails signature'),
            widget=MultilineWidget))

    # Views
    class_views = ['edit']
    edit = ConfigMail_Edit()

    # Configuration
    config_name = 'mail'
    config_group = 'access'


Configuration.register_plugin(ConfigMail)
