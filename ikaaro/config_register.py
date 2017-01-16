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
from itools.core import proto_lazy_property
from itools.datatypes import DateTime, Date, Time
from itools.gettext import MSG
from itools.html import stream_is_empty
from itools.web import STLView

# Import from ikaaro
from autoedit import AutoEdit
from autoform import AutoForm, Widget
from config import Configuration
from config_captcha import Captcha_Field
from datatypes import BirthDate
from datatypes import Days, Months, Years
from emails import send_email
from fields import Boolean_Field, HTMLFile_Field
from resource_ import DBResource


class TermsOfService_View(STLView):

    access = 'is_allowed_to_register'

    def GET(self, resource, context):
        context.content_type = 'text/html; charset=UTF-8'
        config = resource.get_resource('/config/register')
        return config.get_value('tos').to_str()



class TermsOfService_Widget(Widget):

    template = '/ui/register_terms_of_service.xml'
    title = MSG(u'Terms of Service')
    inline = True



class RegisterForm(AutoForm):

    access = 'is_allowed_to_register'
    title = MSG(u'Create an account')

    form_id = 'register-form'
    fields = ['firstname', 'lastname', 'email', 'captcha', 'tos']

    tos_widget = TermsOfService_Widget('tos')
    tos = Boolean_Field(required=True, widget=tos_widget, persistent=False)

    @proto_lazy_property
    def _resource_class(self):
        return self.context.database.get_resource_class('user')


    def get_field(self, name):
        # Captcha
        if name == 'captcha':
            return Captcha_Field(persistent=False)

        # Terms of service
        if name == 'tos':
            # 1. Check the terms-of-service have been filled
            config_register = self.resource.get_resource('config/register')
            tos = config_register.get_value('tos')
            if tos is None:
                return None
            tos = tos.get_body()
            if tos is None:
                return None
            tos = tos.get_content_elements()
            if stream_is_empty(tos):
                return None

            # 2. Ok
            return self.tos

        # Standard
        return self._resource_class.get_field(name)


    def get_schema(self, resource, context):
        schema = {}
        for name in self.fields:
            field = self.get_field(name)
            if field is None:
                continue

            datatype = field.get_datatype()
            schema[name] = datatype

            # Special case: datetime
            if issubclass(datatype, DateTime):
                schema[name] = Date
                schema['%s_time' % name] = Time
                continue
            # Special case: birthdate
            elif issubclass(datatype, BirthDate):
                schema[name] = BirthDate
                schema['%s_day' % name] = Days
                schema['%s_month' % name] = Months
                schema['%s_year' % name] = Years

        return schema


    def get_widgets(self, resource, context):
        widgets = []
        for name in self.fields:
            field = self.get_field(name)
            if field is None:
                continue

            widget = field.get_widget(name)
            widgets.append(widget)

        return widgets


    def set_value(self, resource, context, name, form):
        resource.set_value(name, form[name])


    def action(self, resource, context, form):
        email = form['email'].strip()

        # 1. Make the user, or get it
        results = context.database.search(format='user', email=email)
        if len(results) == 0:
            # New user
            user = context.root.make_user()
            for name in self.fields:
                field = self.get_field(name)
                if field and getattr(field, 'persistent', True):
                    self.set_value(user, context, name, form)

            user.update_pending_key()
            email_id = 'user-ask-for-confirmation'
        else:
            # User already registered
            user = results.get_resources().next()
            email_id = 'register-already-registered'

        # 2. Send email
        send_email(email_id, context, email, user=user)

        # 3. Show message
        message = MSG(
            u'<div id="registration-end-msg">'
            u'An email has been sent to you, to finish the registration '
            u'process follow the instructions detailed in it.</div>')
        return message.gettext().encode('utf-8')



class ConfigRegister(DBResource):

    class_id = 'config-register'
    class_title = MSG(u'User registration')
    class_description = MSG(u'Configuration of the user registration process.')
    class_icon48 = 'icons/48x48/signin.png'

    # Fields
    is_open = Boolean_Field(default=False,
                            title=MSG(u'Users can register by themselves'))
    tos = HTMLFile_Field(title=MSG(u"Terms of service"))

    # Views
    class_views = ['edit']
    edit = AutoEdit(title=class_title, fields=['is_open', 'tos'])

    # Configuration
    config_name = 'register'
    config_group = 'access'


Configuration.register_module(ConfigRegister)
