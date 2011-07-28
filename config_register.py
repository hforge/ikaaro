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
from itools.datatypes import Boolean, DateTime, Date, Time
from itools.gettext import MSG

# Import from ikaaro
from autoedit import AutoEdit
from autoform import AutoForm, Widget
from config import Configuration
from datatypes import BirthDate
from enumerates import Days, Months, Years
from fields import Boolean_Field, Textarea_Field
from resource_ import DBResource
from utils import make_stl_template


class TermsOfService_Widget(Widget):

    title = MSG(u'Terms of Service')

    template = make_stl_template("""
    <textarea cols="80" rows="7" readonly="readonly">${terms_of_service}</textarea>
    <br/>
    <input type="checkbox" id="terms_of_service" name="terms_of_service"
      value="1" />
    <label for="terms_of_service">
      Please check this box to accept the
      <a href="/;terms_of_service" target="_blank">Terms of Service</a>.
    </label>""")



class RegisterForm(AutoForm):

    access = 'is_allowed_to_register'
    title = MSG(u'Create an account')

    fields = ['firstname', 'lastname', 'email']


    def get_schema(self, resource, context):
        cls = context.database.get_resource_class('user')

        schema = {}
        for name in self.fields:
            datatype = cls.get_field(name).get_datatype()
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

        # Terms of service
        config_register = resource.get_resource('config/register')
        terms_of_service = config_register.get_value('terms_of_service')
        if terms_of_service:
            schema['terms_of_service'] = Boolean(mandatory=True)

        return schema


    def get_widgets(self, resource, context):
        cls = context.database.get_resource_class('user')

        widgets = []
        for name in self.fields:
            field = cls.get_field(name)
            widget = field.widget(name, title=field.title)
            widgets.append(widget)

        # Terms of service
        config_register = resource.get_resource('config/register')
        terms_of_service = config_register.get_value('terms_of_service')
        if terms_of_service:
            widget = TermsOfService_Widget('terms_of_service',
                                           terms_of_service=terms_of_service)
            widgets.append(widget)

        return widgets


    def action(self, resource, context, form):
        email = form['email'].strip()
        results = context.root.search(format='user', email=email)
        if len(results) == 0:
            # Create the user
            site_root = context.site_root
            user = site_root.make_user()
            for field in self.fields:
                user.set_property(field, form[field])

            # Send confirmation email
            user.send_confirmation(context, email)
        else:
            user = results.get_documents()[0]
            user = resource.get_resource(user.abspath)
            # TODO Send specific email

        # Bring the user to the login form
        message = MSG(
            u'<div id="registration-end-msg">'
            u'An email has been sent to you, to finish the registration '
            u'process follow the instructions detailed in it.</div>')
        return message.gettext().encode('utf-8')



class ConfigRegister(DBResource):

    class_id = 'config-register'
    class_title = MSG(u'User registration')
    class_description = MSG(u'Configuration the user registration process.')
    class_icon48 = 'icons/48x48/signin.png'

    fields = DBResource.fields + ['is_open', 'terms_of_service']
    is_open = Boolean_Field(default=False,
                            title=MSG(u'Users can register by themselves'))
    terms_of_service = Textarea_Field(title=MSG(u"Terms of service"))

    # Views
    class_views = ['edit']
    edit = AutoEdit(title=class_description,
                    fields=['is_open', 'terms_of_service'])

    # Configuration
    config_name = 'register'
    config_group = 'access'


Configuration.register_plugin(ConfigRegister)
