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
from itools.datatypes import Enumerate
from itools.gettext import MSG
from itools.web import get_context

# Import from ikaaro
from autoedit import AutoEdit
from config import Configuration
from fields import Boolean_Field, Select_Field, Text_Field, Textarea_Field
from resource_ import DBResource



class ContactsOptions(Enumerate):

    @classmethod
    def get_options(cls):
        root = get_context().root

        options = []
        for user in root.get_resources('/users'):
            user_title = user.get_title()
            user_email = user.get_value('email')
            if user_title != user_email:
                user_title = '%s <%s>' % (user_title, user_email)
            else:
                user_title = user_email
            options.append({'name': user.name, 'value': user_title,
                            'sort_value': user_title.lower()})
        options.sort(key=itemgetter('sort_value'))
        return options



mail_description = MSG(u'Configure the website email options')


class ConfigMail_Edit(AutoEdit):

    title = MSG(u'Email options')
    description = mail_description
    fields = ['emails_from_addr', 'emails_reply_to', 'emails_signature',
              'contacts']



class ConfigMail(DBResource):

    class_id = 'config-mail'
    class_title = MSG(u'Email options')
    class_description = mail_description
    class_icon48 = 'icons/48x48/mail.png'

    # Fields
    contacts = Select_Field(multiple=True, datatype=ContactsOptions,
                            title=MSG(u'Select the contact accounts'),
                            has_empty_option=False)
    emails_from_addr = Text_Field(title=MSG(u'From header'))
    emails_reply_to = Boolean_Field(title=MSG(u'Reply to'), default=True)
    emails_signature = Textarea_Field(title=MSG(u'Signature'))

    # Views
    class_views = ['edit']
    edit = ConfigMail_Edit

    # Configuration
    config_name = 'mail'
    config_group = 'access'


Configuration.register_module(ConfigMail)
