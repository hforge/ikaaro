# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
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
from email.charset import add_charset, add_codec, QP
from email.MIMEText import MIMEText
from email.MIMEMultipart import MIMEMultipart
from email.Utils import formatdate
from email.header import Header
from time import time
import traceback
from types import GeneratorType

# Import from itools
from itools import get_abspath
from itools.gettext import MSG
from itools.handlers import File, ConfigFile, Folder as FolderHandler
from itools.html import stream_to_str_as_html
from itools.stl import stl
from itools.uri import Path
from itools.web import get_context, STLView
from itools.xml import XMLParser

# Import from ikaaro
from access import RoleAware
from base import DBObject
from text import PO
from users import UserFolder
from website import WebSite
from html import WebPage
from registry import register_object_class, get_object_class
from folder import Folder
from skins import UI, ui_path
from utils import crypt_password


# itools source and target languages
config = get_abspath(globals(), 'setup.conf')
config = ConfigFile(config)
itools_source_language = config.get_value('source_language')
itools_target_languages = config.get_value('target_languages')


# Force email to send UTF-8 mails in plain text
add_charset('utf-8', QP, None, 'utf-8')
add_codec('utf-8', 'utf_8')



class NotFoundView(STLView):

    template = '/ui/root/not_found.xml'

    def get_namespace(self, model, context):
        namespace = {'uri': str(context.uri)}

        # Don't show the skin if it is not going to work
        request = context.request
        if request.has_header('x-base-path'):
            try:
                model.get_object('%s/ui' % request.get_header('x-base-path'))
            except LookupError:
                response = context.response
                response.set_header('content-type', 'text/html; charset=UTF-8')

        return namespace



class Root(WebSite):

    class_id = 'iKaaro'
    class_version = '20071215'
    class_title = MSG(u'iKaaro', __name__)
    class_icon16 = 'icons/16x16/root.png'
    class_icon48 = 'icons/48x48/root.png'
    class_views = [
        ['browse_content', 'preview_content'],
        ['new_resource'],
        ['edit_metadata'],
        ['control_panel',
         'permissions',
         'new_user',
         'edit_virtual_hosts',
         'edit_security_policy',
         'languages_form',
         'edit_contact_options'],
        ['last_changes']]

    __fixed_handlers__ = ['users', 'ui']


    __roles__ = [
        {'name': 'admins', 'title': MSG(u'Admin', __name__)}]


    @staticmethod
    def _make_object(cls, folder, email, password):
        # The metadata
        metadata = cls.build_metadata(admins=('0',))
        folder.set_handler('.metadata', metadata)
        # User Folder
        users = UserFolder.build_metadata(title={'en': u'Users'})
        folder.set_handler('users.metadata', users)
        # Default User
        password = crypt_password(password)
        user_class = get_object_class('user')
        user = user_class.build_metadata(email=email, password=password)
        folder.set_handler('users/0.metadata', user)
        # Return
        return cls(metadata)


    @classmethod
    def get_metadata_schema(cls):
        schema = WebSite.get_metadata_schema()
        del schema['guests']
        del schema['members']
        del schema['reviewers']
        return schema


    ########################################################################
    # Override itools.web.root.Root
    ########################################################################
    def init(self, context):
        # Set the list of needed resources. The method we are going to
        # call may need external resources to be rendered properly, for
        # example it could need an style sheet or a javascript file to
        # be included in the html head (which it can not control). This
        # attribute lets the interface to add those resources.
        context.styles = []
        context.scripts = []
        context.message = None


    def get_user(self, name):
        users = self.get_object('users')
        if users.has_object(name):
            return users.get_object(name)
        return None


    def after_traverse(self, context, body):
        # If there is not content type and the body is not None,
        # wrap it in the skin template
        if context.response.has_header('Content-Type'):
            if isinstance(body, (list, GeneratorType, XMLParser)):
                body = stream_to_str_as_html(body)
            return body

        if isinstance(body, str):
            body = XMLParser(body)
        return self.get_skin().template(body)


    ########################################################################
    # Publish
    ########################################################################
    def forbidden(self, context):
        message = (u'Access forbidden, you are not authorized to access'
                   u' this resource.')
        return self.gettext(message).encode('utf-8')


    def internal_server_error(self, context):
        namespace = {'traceback': traceback.format_exc()}

        handler = self.get_object('/ui/root/internal_server_error.xml')
        return stl(handler, namespace, mode='html')


    ########################################################################
    # Traverse
    ########################################################################
    def _get_object(self, name):
        if name == 'ui':
            ui = UI(ui_path)
            ui.database = self.metadata.database
            return ui
        return Folder._get_object(self, name)


    def _get_names(self):
        names = [ x for x in Folder._get_names(self) if x ]
        return names + ['ui']


    ########################################################################
    # API
    ########################################################################
    def get_document_types(self):
        return WebSite.get_document_types(self) + [WebSite]


    ########################################################################
    # Search
    def search(self, query=None, **kw):
        catalog = get_context().server.catalog
        return catalog.search(query, **kw)


    ########################################################################
    # Skins
    def get_skin(self):
        context = get_context()
        # Back-Office
        hostname = context.uri.authority.host
        if hostname[:3] in ['bo.', 'bo-']:
            return self.get_object('ui/aruni')
        # Fron-Office
        skin = context.site_root.class_skin
        return self.get_object(skin)


    def get_available_languages(self):
        """Returns the language codes for the user interface.
        """
        source = itools_source_language
        target = itools_target_languages
        # A package based on itools
        cls = self.__class__
        if cls is not Root:
            exec('import %s as pkg' % cls.__module__.split('.', 1)[0])
            config = Path(pkg.__path__[0]).resolve2('setup.conf')
            config = ConfigFile(str(config))
            source = config.get_value('source_language', default=source)
            target = config.get_value('target_languages', default=target)

        target = target.split()
        if source in target:
            target.remove(source)

        target.insert(0, source)
        return target


    ########################################################################
    # Email
    def send_email(self, to_addr, subject, from_addr=None, text=None,
                   html=None, encoding='utf-8', subject_with_host=True,
                   return_receipt=False):
        # Check input data
        if not isinstance(subject, unicode):
            raise TypeError, 'the subject must be a Unicode string'
        if len(subject.splitlines()) > 1:
            raise ValueError, 'the subject cannot have more than one line'
        if text and not isinstance(text, unicode):
            raise TypeError, 'the text must be a Unicode string'
        if html and not isinstance(html, unicode):
            raise TypeError, 'the html must be a Unicode string'

        # Figure out the from address
        context = get_context()
        server = context.server
        if from_addr is None:
            user = context.user
            if user is not None:
                from_addr = user.get_property('email')
            if not from_addr:
                from_addr = server.contact_email

        # Set the subject
        subject = subject.encode(encoding)
        if subject_with_host is True:
            host = context.uri.authority.host
            subject = '[%s] %s' % (host, subject)
        # Build the message
        message = MIMEMultipart('related')
        message['Subject'] = subject
        message['Date'] = formatdate(localtime=True)
        message['From'] = from_addr
        if isinstance(to_addr, tuple):
            real_name, address = to_addr
            to_addr = '%s <%s>' % (Header(real_name, encoding), address)
        message['To'] = to_addr
        # Return Receipt
        if return_receipt is True:
            # Somewhat standard
            message['Disposition-Notification-To'] = from_addr
            # XXX For Outlook 2000
            message['Return-Receipt-To'] = from_addr
        # Create MIMEText
        if html:
            html = html.encode(encoding)
            message_html = MIMEText(html, 'html', _charset=encoding)
        if text:
            text = text.encode(encoding)
            message_text = MIMEText(text, _charset=encoding)
        # Attach MIMETEXT to message
        if text and html:
            message_alternative = MIMEMultipart('alternative')
            message.attach(message_alternative)
            message_alternative.attach(message_text)
            message_alternative.attach(message_html)
        elif html:
            message.attach(message_html)
        elif text:
            message.attach(message_text)
        # Send email
        server.send_email(message)


    not_found = NotFoundView()


###########################################################################
# Register
###########################################################################
register_object_class(Root)
