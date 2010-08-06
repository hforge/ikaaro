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

# Import from itools
from itools.core import get_abspath, merge_dicts
from itools.csv import Property
from itools.datatypes import Email, String, Unicode
from itools.datatypes import Enumerate
from itools.gettext import MSG
from itools.fs import lfs
from itools.web import STLView, INFO, ERROR

# Import from ikaaro
from autoform import AutoForm, SelectWidget, MultilineWidget, TextWidget
from config import get_config
from messages import MSG_NEW_RESOURCE
from registry import get_resource_class
from views_new import ProxyNewInstance



class NotFoundView(STLView):
    template = '/ui/root/not_found.xml'

    def get_namespace(self, resource, context):
        return {'uri': str(context.uri)}


class ForbiddenView(STLView):
    template = '/ui/root/forbidden.xml'

    def POST(self, resource, context):
        return self.GET



class ContactOptions(Enumerate):

    def get_options(cls):
        resource = cls.resource
        users = resource.get_resource('/users')
        options = []
        for name in resource.get_property('contacts'):
            user = users.get_resource(name, soft=True)
            if user is None:
                continue
            options.append({'name': name, 'value': user.get_title()})
        return options



class ContactForm(AutoForm):

    access = True
    title = MSG(u'Contact')
    submit_value = MSG(u'Send')
    query_schema = {'to': String,
                    'subject': Unicode,
                    'message_body': Unicode}

    def get_schema(self, resource, context):
        return {
            'to': ContactOptions(resource=resource, mandatory=True),
            'from': Email(mandatory=True),
            'subject': Unicode(mandatory=True),
            'message_body': Unicode(mandatory=True),
            'captcha_answer': Unicode(mandatory=True),
        }


    def get_widgets(self, resource, context):
        captcha_question = resource.get_property('captcha_question')
        captcha_title = MSG(u"Please answer this: {captcha_question}")
        captcha_title = captcha_title.gettext(
                captcha_question=captcha_question)

        if len(ContactOptions(resource=resource).get_options()) == 1:
            to = SelectWidget('to', title=MSG(u'Recipient'),
                              has_empty_option=False)
        else:
            to = SelectWidget('to', title=MSG(u'Recipient'))

        return [
            to,
            TextWidget('from', title=MSG(u'Your email address'), size=40),
            TextWidget('subject', title=MSG(u'Message subject'), size=40),
            MultilineWidget('message_body', title=MSG(u'Message body'),
                            rows=8, cols=50),
            TextWidget('captcha_answer', title=captcha_title)]


    def get_value(self, resource, context, name, datatype):
        if name == 'from':
            user = context.user
            if user is not None:
                return user.get_property('email')
        else:
            query = context.query
            if name in query:
                return query[name]
        return datatype.get_default()


    def action(self, resource, context, form):
        # Check captcha first
        captcha_answer = form['captcha_answer'].strip()
        expected = resource.get_property('captcha_answer')
        if captcha_answer != expected:
            context.message = ERROR(u"Wrong answer to the question.")
            return
        # Get form values
        contact = form['to']
        from_addr = form['from'].strip()
        subject = form['subject'].strip()
        body = form['message_body'].strip()

        # Find out the "to" address
        contact = resource.get_resource('/users/%s' % contact)
        contact_title = contact.get_title()
        contact = contact.get_property('email')
        if contact_title != contact:
            contact = (contact_title, contact)
        # Send the email
        root = resource.get_root()
        root.send_email(contact, subject, from_addr=from_addr, text=body)
        # Ok
        context.message = INFO(u'Message sent.')



class AboutView(STLView):

    access = True
    title = MSG(u'About')
    template = '/ui/root/about.xml'


    def get_namespace(self, resource, context):
        # Python, itools & ikaaro
        packages = ['sys', 'itools', 'ikaaro']
        config = get_config(context.server.target)
        packages.extend(config.get_value('modules'))
        # Try packages we frequently use
        packages.extend([
            'gio', 'xapian', 'pywin32', 'PIL.Image', 'docutils', 'reportlab',
            'xlrd', 'lpod'])
        # Mapping from package to version attribute
        package2version = {
            'gio': 'pygio_version',
            'xapian': 'version_string',
            'PIL.Image': 'VERSION',
            'reportlab': 'Version',
            'sys': 'version_info',
            'xlrd': '__VERSION__'}
        package2title = {
            'gio': u'pygobject',
            'lpod': u'lpOD',
            'sys': u'Python',
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
            'linux2': u'GNU/Linux',
            'darwin': u'Mac OS X',
            'win32': u'Windows'}.get(sys.platform, sys.platform)
        packages_ns.insert(0,
            {'name': MSG(u'Operating System'), 'version': platform})

        namespace = {'packages': packages_ns}
        return namespace



class CreditsView(STLView):

    access = True
    title = MSG(u'Credits')
    template = '/ui/root/credits.xml'
    styles = ['/ui/credits.css']


    def get_namespace(self, resource, context):
        # Build the namespace
        credits = get_abspath('CREDITS')
        lines = lfs.open(credits).readlines()
        names = [ x[3:].strip() for x in lines if x.startswith('N: ') ]

        return {'hackers': names}



class WebSite_NewInstance(ProxyNewInstance):

    template = '/ui/website/new_instance.xml.en'

    schema = merge_dicts(ProxyNewInstance.schema, vhosts=String)

    def get_namespace(self, resource, context):
        namespace = ProxyNewInstance.get_namespace(self, resource, context)
        # Add vhosts
        vhosts = context.get_form_value('vhosts')
        namespace['vhosts'] = vhosts

        return namespace


    def action(self, resource, context, form):
        name = form['name']
        title = form['title']
        vhosts = form['vhosts']
        vhosts = [ x.strip() for x in vhosts.splitlines() ]
        vhosts = [ x for x in vhosts if x ]

        # Create the resource
        class_id = form['class_id']
        if class_id is None:
            # Get it from the query
            class_id = context.query['type']
        cls = get_resource_class(class_id)
        child = resource.make_resource(name, cls)
        # The metadata
        metadata = child.metadata
        language = resource.get_content_language(context)
        metadata.set_property('title', Property(title, lang=language))
        metadata.set_property('vhosts', vhosts)

        goto = './%s/' % name
        return context.come_back(MSG_NEW_RESOURCE, goto=goto)

