# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2007-2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007-2008 Nicolas Deram <nicolas@itaapy.com>
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
from email.mime.application import MIMEApplication
from email.MIMEText import MIMEText
from email.MIMEImage import MIMEImage
from email.MIMEMultipart import MIMEMultipart
from email.Utils import formatdate
from email.header import Header
from json import dumps
import sys
import traceback

# Import from itools
from itools.core import get_abspath
from itools.datatypes import String
from itools.gettext import MSG
from itools.handlers import ConfigFile, ro_database
from itools.stl import stl
from itools.uri import Path
from itools.web import BaseView, get_context

# Import from ikaaro
from config import get_config
from database import ReadOnlyDatabase
from folder import Folder
from registry import get_resource_class
from skins import UI, ui_path
from user import UserFolder
from utils import crypt_password
from website import WebSite


# itools source and target languages
config = get_abspath('setup.conf')
config = ro_database.get_handler(config,  ConfigFile)
itools_source_language = config.get_value('source_language')
itools_target_languages = config.get_value('target_languages')


# Force email to send UTF-8 mails in plain text
add_charset('utf-8', QP, None, 'utf-8')
add_codec('utf-8', 'utf_8')



class CtrlView(BaseView):

    access = True
    query_schema = {'name': String}

    def GET(self, resource, context):
        context.content_type = 'text/plain'
        database = context.database
        return dumps(
            {'packages': resource.get_version_of_packages(context),
             'read-only': type(database) is ReadOnlyDatabase})



class Root(WebSite):

    class_id = 'iKaaro'
    class_title = MSG(u'iKaaro')
    class_icon16 = 'icons/16x16/root.png'
    class_icon48 = 'icons/48x48/root.png'
    class_control_panel = ['browse_users', 'add_user', 'edit_virtual_hosts',
                           'edit_security_policy', 'edit_languages',
                           'edit_contact_options', 'edit_seo']


    __fixed_handlers__ = ['users', 'ui']


    __roles__ = [
        {'name': 'admins', 'title': MSG(u'Admin')}]


    @staticmethod
    def _make_resource(cls, folder, email, password, **kw):
        # The metadata
        metadata = cls.build_metadata(admins=('0',), **kw)
        folder.set_handler('.metadata', metadata)
        # User Folder
        users = UserFolder.build_metadata(title={'en': u'Users'})
        folder.set_handler('users.metadata', users)
        # Default User
        password = crypt_password(password)
        user_class = get_resource_class('user')
        user = user_class.build_metadata(email=email, password=password)
        folder.set_handler('users/0.metadata', user)
        # Return
        return cls(metadata)


    ########################################################################
    # Override itools.web.root.Root
    ########################################################################
    def get_user(self, name):
        return self.get_resource('users/%s' % name, soft=True)


    def get_user_from_login(self, username):
        """Return the user identified by its unique e-mail or username, or
        return None.
        """
        # Search the user by username (login name)
        results = self.search(username=username)
        n = len(results)
        if n == 0:
            return None
        if n > 1:
            error = 'There are %s users in the database identified as "%s"'
            raise ValueError, error % (n, username)
        # Get the user
        brain = results.get_documents()[0]
        return self.get_user(brain.name)


    def get_user_title(self, username):
        if username is None:
            return None
        users = self.get_resource('users')
        user = users.get_resource(username, soft=True)
        if user is None:
            return username
        return user.get_title()


    ########################################################################
    # Publish
    ########################################################################
    def internal_server_error(self, context):
        namespace = {'traceback': traceback.format_exc()}

        handler = self.get_resource('/ui/root/internal_server_error.xml')
        return stl(handler, namespace, mode='html')


    ########################################################################
    # Traverse
    ########################################################################
    def _get_resource(self, name):
        if name == 'ui':
            ui = UI(ui_path)
            return ui
        return Folder._get_resource(self, name)


    def _get_names(self):
        names = [ x for x in Folder._get_names(self) if x ]
        return names + ['ui']


    ########################################################################
    # API
    ########################################################################
    def get_document_types(self):
        return WebSite.get_document_types(self) + [WebSite]


    def get_available_languages(self):
        """Returns the language codes for the user interface.
        """
        source = itools_source_language
        target = itools_target_languages
        # A package based on itools
        cls = self.__class__
        if cls is not Root:
            exec('import %s as pkg' % cls.__module__.split('.', 1)[0])
            config = Path(pkg.__path__[0]).resolve_name('setup.conf')
            config = ro_database.get_handler(str(config), ConfigFile)
            source = config.get_value('source_language', default=source)
            target = config.get_value('target_languages', default=target)

        target = target.split()
        if source in target:
            target.remove(source)

        target.insert(0, source)
        return target


    def get_version_of_packages(self, context):
        versions = {}
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
            'sys': 'version',
            'xlrd': '__VERSION__'}

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
                version = None
                MSG(u'no version found').gettext()
            else:
                if hasattr(version, '__call__'):
                    version = version()
                if isinstance(version, tuple):
                    version = '.'.join([str(v) for v in version])
            # Ok
            versions[name] = version

        # Insert first the platform
        versions['os'] = {
            'linux2': u'GNU/Linux',
            'darwin': u'Mac OS X',
            'win32': u'Windows'}.get(sys.platform, sys.platform)
        return versions

    ########################################################################
    # Search
    def search(self, query=None, **kw):
        catalog = get_context().database.catalog
        return catalog.search(query, **kw)


    ########################################################################
    # Email
    def send_email(self, to_addr, subject, from_addr=None, text=None,
                   html=None, encoding='utf-8', subject_with_host=True,
                   return_receipt=False, attachment=None):
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
        site_root = context.site_root
        if from_addr is None:
            user = context.user
            if user is not None:
                from_addr = user.get_title(), user.get_property('email')
            elif site_root.get_property('emails_from_addr'):
                user_name = site_root.get_property('emails_from_addr')
                user = self.get_resource('/users/%s' % user_name)
                from_addr = user.get_title(), user.get_property('email')
            else:
                from_addr = server.smtp_from

        # Set the subject
        subject = subject.encode(encoding)
        if subject_with_host is True:
            subject = '[%s] %s' % (context.uri.authority, subject)
        # Add signature
        if site_root.get_property('emails_signature'):
            text += '\n\n-- \n%s' % site_root.get_property('emails_signature')
        # Build the message
        message = MIMEMultipart('related')
        message['Subject'] = Header(subject, encoding)
        message['Date'] = formatdate(localtime=True)

        for key, addr in [('From', from_addr), ('To', to_addr)]:
            if isinstance(addr, tuple):
                real_name, address = addr
                addr = '%s <%s>' % (Header(real_name, encoding), address)
            message[key] = addr
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
        # Attach attachment
        if attachment:
            subtype = attachment.get_mimetype()
            data = attachment.to_str()
            if subtype[:6] == 'image/':
                subtype = subtype[6:]
                mime_cls = MIMEImage
            else:
                mime_cls = MIMEApplication
            message_attachment = mime_cls(data, subtype)
            message_attachment.add_header('Content-Disposition', 'attachment',
                                          filename=attachment.name)
            message.attach(message_attachment)
        # Send email
        server.send_email(message)


    #######################################################################
    # Web services
    #######################################################################
    _ctrl = CtrlView()

