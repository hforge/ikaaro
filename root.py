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
from decimal import Decimal
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
from itools.core import get_abspath, is_prototype
from itools.database import RWDatabase
from itools.gettext import MSG
from itools.handlers import ConfigFile, ro_database
from itools.html import stream_is_empty, stream_to_str_as_html, xhtml_doctype
from itools.log import log_warning
from itools.stl import stl
from itools.uri import Path
from itools.web import BaseView, get_context
from itools.xml import XMLParser, is_xml_stream

# Import from ikaaro
from config import Configuration
from config_register import RegisterForm, TermsOfService_View
from fields import Char_Field
from folder import Folder
from resource_views import LoginView
from skins import skin_registry
from root_views import PoweredBy, ContactForm
from root_views import NotFoundView, ForbiddenView
from root_views import UploadStatsView, UpdateDocs


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

    def GET(self, resource, context):
        context.content_type = 'text/plain'
        database = context.database
        return dumps(
            {'packages': resource.get_version_of_packages(context),
             'read-only': not isinstance(database, RWDatabase)})



###########################################################################
# Resource
###########################################################################
class Root(Folder):

    class_id = 'iKaaro'
    class_version = '20100702'
    #class_version = '20120601'
    class_title = MSG(u'iKaaro')
    class_icon16 = 'icons/16x16/root.png'
    class_icon48 = 'icons/48x48/root.png'
    class_skin = 'aruni'

    abspath = Path('/')

    # Fields
    website_languages = Char_Field(multiple=True, default=['en'])

    is_content = True


    def init_resource(self, email, password):
        super(Root, self).init_resource()
        # Configuration
        title = {'en': u'Configuration'}
        self.make_resource('config', Configuration, title=title)
        # First user
        user = self.make_user(email, password)
        user.set_value('groups', ['/config/groups/admins'])


    def make_resource(self, name, cls, **kw):
        if name == 'ui':
            raise ValueError, 'cannot add a resource with the name "ui"'
        return super(Root, self).make_resource(name, cls, **kw)


    ########################################################################
    # Override itools.web.root.Root
    ########################################################################
    def get_user_title(self, userid):
        if not userid:
            return None

        # Userid (abspath) or username
        if userid[0] != '/':
            userid = '/users/%s' % userid

        # Get user
        user = self.get_resource(userid, soft=True)
        if user is None:
            username = userid.rsplit('/', 1)[-1]
            log_warning('unkwnown user %s' % username, domain='ikaaro')
            return unicode(username)

        # Ok
        return user.get_title()


    ########################################################################
    # Publish
    ########################################################################
    def internal_server_error(self, context):
        # Send email (TODO Move this to the itools.log system)
        self.alert_on_internal_server_error(context)

        # Ok
        namespace = {'traceback': traceback.format_exc()}
        handler = context.get_template('/ui/root/internal_server_error.xml')
        return stl(handler, namespace, mode='html')


    def alert_on_internal_server_error(self, context):
        # TODO Move this to the itools.log system
        # Get email address
        email = context.server.config.get_value('log-email')
        # We send an email with the traceback
        if email:
            headers = u'\n'.join([u'%s => %s' % (x, y)
                                    for x, y in context.get_headers()])
            subject = MSG(u'Internal server error').gettext()
            text = u'%s\n\n%s\n\n%s' % (context.uri,
                                        traceback.format_exc(),
                                        headers)
            self.send_email(email, subject, text=text)


    ########################################################################
    # Traverse
    ########################################################################
    def _get_names(self):
        return [ x for x in super(Root, self)._get_names() if x ]


    ########################################################################
    # API
    ########################################################################
    def get_default_language(self):
        return self.get_value('website_languages')[0]


    def get_default_edit_languages(self):
        return [self.get_default_language()]


    def before_traverse(self, context, min=Decimal('0.000001'),
                        zero=Decimal('0.0')):
        # Set the language cookie if specified by the query.
        # NOTE We do it this way, instead of through a specific action,
        # to avoid redirections.
        language = context.get_form_value('language')
        if language is not None and language != '':
            context.set_cookie('language', language)

        # The default language (give a minimum weight)
        accept = context.accept_language
        default = self.get_default_language()
        if accept.get(default, zero) < min:
            accept.set(default, min)
        # User Profile (2.0)
        user = context.user
        if user is not None:
            language = user.get_value('user_language')
            if language is not None:
                accept.set(language, 2.0)
        # Cookie (2.5)
        language = context.get_cookie('language')
        if language is not None and language != '':
            accept.set(language, 2.5)


    def get_skin(self, context):
        # Open in fancybox ?
        if (getattr(context.view, 'can_be_open_in_fancybox', False)
            and 'fancybox' in context.uri.query):
            return skin_registry['fancybox']
        # Back-Office
        hostname = context.uri.authority
        if hostname[:3] in ['bo.', 'bo-']:
            return skin_registry['aruni']
        # Fron-Office
        return skin_registry[self.class_skin]


    def after_traverse(self, context):
        body = context.entity
        is_str = type(body) is str
        is_xml = is_xml_stream(body)
        if not is_str and not is_xml:
            return

        # If there is not a content type, just serialize the content
        if context.content_type:
            if is_xml:
                context.entity = stream_to_str_as_html(body)
            return

        # Standard page, wrap the content into the general template
        if is_str:
            body = XMLParser(body, doctype=xhtml_doctype)
        context.entity = self.get_skin(context).template(body)
        context.content_type = 'text/html; charset=UTF-8'


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
        # Python, itools & ikaaro
        packages = ['sys', 'itools', 'ikaaro']
        config = context.server.config
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

        # Namespace
        versions = {}
        for name in packages:
            attribute = package2version.get(name, '__version__')

            # Exception: PIL
            if name == 'PIL.Image':
                name = 'PIL'
                try:
                    package = __import__('Image', fromlist=['PIL'])
                except ImportError:
                    continue
            # XXX Skip stuff like 'ikaaro.blog', etc.
            elif '.' in name:
                continue
            # Common case
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
            else:
                if hasattr(version, '__call__'):
                    version = version()
                if type(version) is tuple or name == 'sys':
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
    # Email
    def send_email(self, to_addr, subject, reply_to=None, text=None,
                   html=None, encoding='utf-8', subject_with_host=True,
                   return_receipt=False, attachment=None):
        # 1. Check input data
        if type(subject) is unicode:
            subject = subject.encode(encoding)
        elif is_prototype(subject, MSG):
            subject = subject.gettext()
        else:
            raise TypeError, 'unexpected subject of type %s' % type(subject)

        if len(subject.splitlines()) > 1:
            raise ValueError, 'the subject cannot have more than one line'
        if text and not isinstance(text, unicode):
            raise TypeError, 'the text must be a Unicode string'
        if html and not isinstance(html, unicode):
            raise TypeError, 'the html must be a Unicode string'

        # 2. Local variables
        context = get_context()
        server = context.server
        mail = self.get_resource('/config/mail')

        # 3. Start the message
        message = MIMEMultipart('related')
        message['Date'] = formatdate(localtime=True)

        # 4. From
        from_addr = mail.get_value('emails_from_addr').strip()
        if from_addr:
            # FIXME Parse the address and use Header
            message['From'] = from_addr.encode(encoding)
        else:
            message['From'] = server.smtp_from

        # 5. To
        if isinstance(to_addr, tuple):
            real_name, address = to_addr
            to_addr = '%s <%s>' % (Header(real_name, encoding), address)
        message['To'] = to_addr

        # 6. Subject
        if subject_with_host is True:
            subject = '[%s] %s' % (context.uri.authority, subject)
        message['Subject'] = Header(subject, encoding)

        # 7. Reply-To
        if reply_to:
            message['Reply-To'] = reply_to
        elif mail.get_value('emails_reply_to'):
            user = context.user
            if user:
                user_title = Header(user.get_title(), encoding)
                user_email = user.get_value('email')
                message['Reply-To'] = '%s <%s>' % (user_title, user_email)

        # Return Receipt
        if return_receipt and reply_to:
            message['Disposition-Notification-To'] = reply_to # Standard
            message['Return-Receipt-To'] = reply_to           # Outlook 2000

        # 8. Body
        signature = mail.get_value('emails_signature')
        if signature:
            signature = signature.strip()
            if not signature.startswith('--'):
                signature = '-- \n%s' % signature
            text += '\n\n%s' % signature

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

        # 6. Send email
        server.send_email(message)


    #######################################################################
    # Access control
    #######################################################################
    def make_user(self, loginname=None, password=None):
        # Create the user
        users = self.get_resource('/users')
        cls = self.database.get_resource_class('user')
        user = users.make_resource(None, cls)

        # Set login name and paswword
        if loginname is not None:
            user.set_property(user.login_name_property, loginname)
        if password is not None:
            user.set_value('password', password)

        # Return the user
        return user


    def is_allowed_to_register(self, user, resource):
        if user:
            return False
        return self.get_resource('config/register').get_value('is_open')


    def is_admin(self, user, resource):
        if user is None:
            return False

        return '/config/groups/admins' in user.get_value('groups')


    def has_permission(self, user, permission, resource, class_id=None):
        if resource is None:
            return False
        access = self.get_resource('config/access')
        return access.has_permission(user, permission, resource, class_id)


    def is_allowed_to_view(self, user, resource):
        return self.has_permission(user, 'view', resource)


    def is_allowed_to_edit(self, user, resource):
        return self.has_permission(user, 'edit', resource)


    def is_allowed_to_add(self, user, resource):
        return self.has_permission(user, 'add', resource)


    def is_allowed_to_share(self, user, resource):
        return self.has_permission(user, 'share', resource)


    # By default all other change operations (add, remove, copy, etc.)
    # are equivalent to "edit".
    def is_allowed_to_put(self, user, resource):
        return self.has_permission(user, 'edit', resource)


    def is_allowed_to_remove(self, user, resource):
        return self.has_permission(user, 'edit', resource)


    def is_allowed_to_copy(self, user, resource):
        return self.has_permission(user, 'edit', resource)


    def is_allowed_to_move(self, user, resource):
        return self.has_permission(user, 'edit', resource)


    def is_allowed_to_view_folder(self, user, resource):
        stream = resource.get_html_field_body_stream('index')
        if stream_is_empty(stream):
            return False

        return self.is_allowed_to_view(user, resource)


    def get_user(self, name):
        return self.get_resource('users/%s' % name, soft=True)


    def get_user_from_login(self, username):
        """Return the user identified by its unique e-mail or username, or
        return None.
        """
        # Search the user by username (login name)
        database = self.database
        results = database.search(parent_paths='/users', username=username)

        n = len(results)
        if n == 0:
            return None
        if n > 1:
            error = 'There are %s users in the database identified as "%s"'
            raise ValueError, error % (n, username)

        # Get the user
        brain = results.get_documents()[0]
        return self.get_user(brain.name)


    #######################################################################
    # Views
    #######################################################################
    register = RegisterForm
    terms_of_service = TermsOfService_View
    # Public views
    contact = ContactForm
    powered_by = PoweredBy
    # Special
    forbidden = ForbiddenView
    unauthorized = LoginView
    not_found = NotFoundView
    upload_stats = UploadStatsView
    update_docs = UpdateDocs
    _ctrl = CtrlView


    #######################################################################
    # Upgrade
    #######################################################################
#   def update_20120601(self):
#       # Configuration
#       title = {'en': u'Configuration'}
#       self.make_resource('config', Configuration, title=title)

#       # User groups
#       users = self.get_resource('users')
#       for p in self.get_property('admins'):
#           user = users.get_resource(p.value)
#           user.set_value('groups', '/config/groups/admins')
