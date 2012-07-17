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
from getpass import getuser
from json import dumps
from socket import gethostname

# Import from itools
from itools.core import get_abspath
from itools.datatypes import Email, String, Unicode, Integer
from itools.datatypes import Enumerate
from itools.fs import lfs, FileName
from itools.gettext import MSG
from itools.handlers import get_handler_class_by_mimetype
from itools.html import XHTMLFile
from itools.stl import rewrite_uris
from itools.uri import get_reference
from itools.web import BaseView, FormError, STLView, INFO
from itools.xml import get_element, TEXT

# Import from ikaaro
from autoform import AutoForm, FileWidget
from autoform import HiddenWidget, SelectWidget, MultilineWidget, TextWidget
from buttons import Button
from config_captcha import CaptchaDatatype, CaptchaWidget
from datatypes import FileDataType
from ikaaro.folder import Folder
from messages import MSG_UNEXPECTED_MIMETYPE



class NotFoundView(STLView):
    template = '/ui/root/not_found.xml'

    def get_namespace(self, resource, context):
        return {'uri': str(context.uri)}


class ForbiddenView(STLView):
    template = '/ui/root/forbidden.xml'

    def POST(self, resource, context):
        return self.GET



class UploadStatsView(BaseView):

    access = True
    query_schema = {'upload_id': Integer}

    def GET(self, resource, context):
        context.content_type = 'text/plain'

        upload_id = context.query.get('upload_id')
        if upload_id is None:
            return dumps({'valid_id': False})

        stats = context.server.upload_stats.get(upload_id)
        if stats is None:
            return dumps({'valid_id': False})

        uploaded_size, total_size = stats
        return dumps({'valid_id': True,
                      'uploaded_size': uploaded_size,
                      'total_size': total_size})



class ContactOptions(Enumerate):

    def get_options(cls):
        resource = cls.resource

        users = resource.get_resource('/users')
        mail = resource.get_resource('/config/mail')

        options = []
        for name in mail.get_value('contacts'):
            user = users.get_resource(name, soft=True)
            if user is None:
                continue
            title = user.get_title()
            options.append({'name': name, 'value': title,
                            'sort_value': title.lower()})
        options.sort(key=lambda x: x['sort_value'])
        return options



class ContactForm(AutoForm):

    access = True
    title = MSG(u'Contact')
    actions = [Button(access=True, css='button-ok', title=MSG(u'Send'))]
    query_schema = {'to': String,
                    'subject': Unicode,
                    'message_body': Unicode}

    def get_schema(self, resource, context):
        to = ContactOptions(resource=resource, mandatory=True)
        if len(to.get_options()) == 1:
            to = String(mandatory=True)

        return {
            'to': to,
            'from': Email(mandatory=True),
            'subject': Unicode(mandatory=True),
            'message_body': Unicode(mandatory=True),
            'captcha': CaptchaDatatype}


    def get_widgets(self, resource, context):
        if len(ContactOptions(resource=resource).get_options()) == 1:
            to = HiddenWidget('to')
        else:
            to = SelectWidget('to', title=MSG(u'Recipient'))

        return [
            to,
            TextWidget('from', title=MSG(u'Your email address'), size=40),
            TextWidget('subject', title=MSG(u'Message subject'), size=40),
            MultilineWidget('message_body', title=MSG(u'Message body'),
                            rows=8, cols=50),
            CaptchaWidget('captcha')]


    def get_value(self, resource, context, name, datatype):
        if name == 'to':
            options = ContactOptions(resource=resource).get_options()
            if len(options) == 1:
                return options[0]['name']

        if name == 'from':
            user = context.user
            if user is not None:
                return user.get_value('email')
            return datatype.get_default()

        query = context.query
        if name in query:
            return query[name]

        return datatype.get_default()


    def action(self, resource, context, form):
        # Get form values
        contact = form['to']
        reply_to = form['from'].strip()
        subject = form['subject'].strip()
        body = form['message_body'].strip()

        # Find out the "to" address
        contact = resource.get_resource('/users/%s' % contact)
        contact_title = contact.get_title()
        contact = contact.get_value('email')
        if contact_title != contact:
            contact = (contact_title, contact)
        # Send the email
        root = resource.get_root()
        root.send_email(contact, subject, reply_to=reply_to, text=body)
        # Ok
        context.message = INFO(u'Message sent.')


class PoweredBy(STLView):

    access = True
    title = MSG(u'Powered by')
    template = '/ui/root/powered-by.xml'


    def get_namespace(self, resource, context):
        namespace = {}
        # Credits
        credits = get_abspath('CREDITS.txt')
        lines = lfs.open(credits).readlines()
        names = [ x[2:].strip() for x in lines if x.startswith('  ') ]
        namespace['hackers'] = names

        # Installed software
        root = context.root
        is_admin = root.is_admin(context.user, resource)
        namespace['is_admin'] = is_admin

        if is_admin:
            package2title = {
                'gio': u'pygobject',
                'lpod': u'lpOD',
                'sys': u'Python',
                'os': MSG(u'Operating System')}
            packages = [
                {'name': package2title.get(x, x),
                 'version': y or MSG('no version found')}
                for x, y in root.get_version_of_packages(context).items() ]

            location = (getuser(), gethostname(), context.server.target)
            namespace['packages'] = packages
            namespace['location'] = u'%s@%s:%s' % location

        # Ok
        return namespace



class UpdateDocs(AutoForm):

    access = 'is_admin'
    title = MSG(u'Update docs')

    schema = {
        'file': FileDataType(mandatory=True),
        'language': String(mandatory=True, default='en')}
    widgets = [
        FileWidget('file'),
        TextWidget('language', title=MSG(u'Language'),
                   tip=MSG(u'"en", "fr", ...'))]

    actions = [
        Button(access='is_admin', css='button-ok', title=MSG(u'Upload'))]


    def _get_form(self, resource, context):
        form = super(UpdateDocs, self)._get_form(resource, context)
        # Check the mimetype
        filename, mimetype, body = form['file']
        if mimetype not in ('application/x-tar', 'application/zip'):
            raise FormError, MSG_UNEXPECTED_MIMETYPE(mimetype=mimetype)

        return form


    def action(self, resource, context, form):
        skip = set(['application/javascript', 'application/octet-stream',
                    'text/css', 'text/plain'])
        keep = set(['application/pdf', 'image/png'])
        language = form['language']

        def rewrite(value):
            if value[0] == '#':
                return value
            ref = get_reference(value)
            if ref.scheme:
                return value
            name = ref.path.get_name()
            name, extension, langage = FileName.decode(name)
            if extension in ('png', 'pdf'):
                name = '%s/;download' % name
            ref.path[-1] = name
            return '../%s' % ref

        def filter(path, mimetype, body):
            # HTML
            if mimetype == 'text/html':
                source = XHTMLFile(string=body)
                target = XHTMLFile()
                elem = get_element(source.events, 'div', **{'class': 'body'})
                if not elem:
                    print 'E', path
                    return None
                elements = elem.get_content_elements()
                elements = rewrite_uris(elements, rewrite)
                elements = list(elements)
                target.set_body(elements)
                return target.to_str()
            # Skip
            elif mimetype in skip:
                return None
            # Keep
            elif mimetype in keep:
                return body
            # Unknown
            else:
                print 'X', path, mimetype
                return body

        def postproc(file):
            # Share
            file.set_value('share', ['everybody'])
            # Title
            if file.class_id != 'webpage':
                return
            handler = file.get_handler()
            events = handler.events
            elem = get_element(events, 'h1')
            if elem:
                title = [
                    unicode(x[1], 'utf8')
                    for x in elem.get_content_elements() if x[0] == TEXT ]
                if title[-1] == u'¶':
                    title.pop()
                title = u''.join(title)
                file.set_property('title', title, language)
                handler.events = events[:elem.start] + events[elem.end+1:]

        # 1. Make the '/docs/' folder
        docs = resource.get_resource('docs', soft=True)
        if not docs:
            docs = resource.make_resource('docs', Folder)
        # 2. Extract
        filename, mimetype, body = form['file']
        cls = get_handler_class_by_mimetype(mimetype)
        handler = cls(string=body)
        docs.extract_archive(handler, language, filter, postproc, True)

        # Ok
        message = MSG(u'Documentation updated.')
        return context.come_back(message, goto='./docs')
