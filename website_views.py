# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007-2008 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2008 Nicolas Deram <nicolas@itaapy.com>
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
import sys
from traceback import format_exc

# Import from itools
from itools.core import get_abspath, thingy_property, thingy_lazy_property
from itools.core import OrderedDict
from itools.datatypes import Email, Enumerate, Unicode
from itools.gettext import MSG
from itools.stl import stl
from itools import vfs
from itools.web import stl_view, INFO, ERROR, FormError
from itools.web import choice_field, email_field, text_field, textarea_field
from itools.xapian import PhraseQuery, OrQuery, AndQuery, split_unicode

# Import from ikaaro
from autoform import AutoForm
import globals



class NotFoundView(stl_view):
    template = 'root/not_found.xml'

    def uri(self):
        return str(self.context.uri)


class ForbiddenView(stl_view):
    template = 'root/forbidden.xml'

    def POST(self, resource, context):
        return self.GET


class InternalServerError(stl_view):
    template = 'root/internal_server_error.xml'

    def traceback(self):
        return format_exc()



class ForgottenPasswordForm(AutoForm):

    access = True
    view_title = MSG(u'Forgotten password')
    submit_value = MSG(u'Ok')

    username = email_field(value='', title=MSG(u'Type your email address'))


    def get_value(self, name):
        if name == 'username':
            return self.context.get_query_value('username')

        return super(ForgottenPasswordForm, self).get_value(name)


    def action(self, resource, context, form):
        # Get the email address
        username = form['username'].strip()

        # Get the user with the given login name
        results = context.search(username=username)
        if len(results) == 0:
            message = ERROR(u'There is not a user identified as "{username}"',
                            username=username)
            context.message = message
            return


        # Send email of confirmation
        user = results.get_documents()[0]
        email = user.get_value('email')
        user.send_forgotten_password(context, email)

        handler = resource.get_resource('/ui/website/forgotten_password.xml')
        return stl(handler)



class RegisterForm(AutoForm):

    access = 'is_allowed_to_register'
    view_title = MSG(u'Register')
    submit_value = MSG(u'Register')

    firstname = text_field(required=True, title=MSG(u'First Name'))
    lastname = text_field(required=True, title=MSG(u'Last Name'))
    email = email_field(required=True, title=MSG(u'E-mail Address'))


    def cook(self, method):
        super(RegisterForm, self).cook(method)
        if method == 'get':
            return

        # Check the user is not yet in the group
        email = self.email.value.strip()
        user = self.context.get_user_by_login(email)
        if user and not user.has_property('user_must_confirm'):
            error = ERROR(u"There's already an active user with that email.")
            self.email.error = error
            raise FormError


    def action(self, resource, context, form):
        # Get input data
        firstname = form['firstname'].strip()
        lastname = form['lastname'].strip()
        email = form['email'].strip()

        # Do we already have a user with that email?
        user = context.get_user_by_login(email)
        if user is None:
            # Add the user
            users = resource.get_resource('users')
            user = users.set_user(email)
            user.set_property('firstname', firstname)
            user.set_property('lastname', lastname)
            # Set the role
            default_role = resource.class_roles[0]
            resource.set_user_role(user.get_name(), default_role)

        # Send confirmation email
        user.send_confirmation(context, email)

        # Bring the user to the login form
        message = MSG(
            u"An email has been sent to you, to finish the registration "
            u"process follow the instructions detailed in it.")
        return message.gettext().encode('utf-8')



class to_field(choice_field):

    @thingy_lazy_property
    def values(self):
        resource = self.view.resource
        users = resource.get_resource('/users')

        values = OrderedDict()
        for username in resource.get_value('contacts'):
            values[username] = users.get_resource(username).get_title()

        return values



class ContactForm(AutoForm):

    access = True
    view_title = MSG(u'Contact')
    submit_value = MSG(u'Send')

    # Fields
    to = to_field(required=True, title = MSG(u'Recipient'))
    subject = text_field(required=True, title=MSG(u'Message subject'))

    message_body = textarea_field(required=True, rows=8, cols=50)
    message_body.title = MSG(u'Message body')

    from_ = email_field(required=True, title=MSG(u'Your email address'))

    field_names = ['to', 'from_', 'subject', 'message_body']


    def get_value(self, field):
        if field.name == 'from_':
            user = self.context.user
            if user:
                return user.get_value('email')

        return super(ContactForm, self).get_value(field)


    def action(self, resource, context, form):
        # Get form values
        contact = form['to']
        from_addr = form['from_'].strip()
        subject = form['subject'].strip()
        body = form['message_body'].strip()

        # Find out the "to" address
        contact = resource.get_resource('/users/%s' % contact)
        contact_title = contact.get_title()
        contact = contact.get_property('email')
        if contact_title != contact:
            contact = (contact_title, contact)
        # Send the email
        context.send_email(contact, subject, from_addr=from_addr, text=body)
        # Ok
        context.message = INFO(u'Message sent.')



class AboutView(stl_view):

    access = True
    view_title = MSG(u'About')
    template = 'root/about.xml'


    def packages(self):
        # Python, itools & ikaaro
        packages = ['sys', 'itools', 'ikaaro']
        config = globals.config
        packages.extend(config.get_value('modules'))
        # Try packages we frequently use
        packages.extend([
            'gio', 'xapian', 'pywin32', 'PIL.Image', 'docutils', 'reportlab',
            'xlrd'])
        # Mapping from package to version attribute
        package2version = {
            'gio': 'pygio_version',
            'xapian': 'version_string',
            'PIL.Image': 'VERSION',
            'reportlab': 'Version',
            'sys': 'version_info',
            'xlrd': '__VERSION__'}
        package2title = {
            'gio': 'pygobject',
            'sys': 'Python',
            }

        # Namespace
        packages_ns = []
        for name in packages:
            attribute = package2version.get(name, '__version__')
            # Import
            if '.' in name:
                name, subname = name.split('.')
                try:
                    package = __import__(subname, fromlist=[name])
                except ImportError:
                    continue
            else:
                try:
                    package = __import__(name)
                except ImportError:
                    continue

            # Version
            try:
                version = getattr(package, attribute)
            except AttributeError:
                version = MSG(u'no version found')
            else:
                if hasattr(version, '__call__'):
                    version = version()
                if isinstance(version, tuple):
                    version = '.'.join([str(v) for v in version])
            # Ok
            title = package2title.get(name, name)
            packages_ns.append({'name': title, 'version': version})

        # Insert first the platform
        platform = {
            'linux2': 'GNU/Linux',
            'darwin': 'Mac OS X',
            'win32': 'Windows'}.get(sys.platform, sys.platform)
        packages_ns.insert(0,
            {'name': MSG(u'Operating System'), 'version': platform})

        return packages_ns



class CreditsView(stl_view):

    access = True
    view_title = MSG(u'Credits')
    template = 'root/credits.xml'
    styles = ['/ui/credits.css']


    def hackers(self):
        credits = get_abspath('CREDITS')
        lines = vfs.open(credits).readlines()
        return [ x[3:].strip() for x in lines if x.startswith('N: ') ]

