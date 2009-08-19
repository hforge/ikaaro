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
from email.MIMEText import MIMEText
from email.MIMEMultipart import MIMEMultipart
from email.Utils import formatdate
from email.header import Header

# Import from itools
from itools.core import get_abspath
from itools.datatypes import String
from itools.gettext import MSG
from itools.handlers import ConfigFile, RWDatabase
from itools.http import get_context
from itools.stl import stl
from itools.uri import Path
from itools.web import BaseView

# Import from ikaaro
from folder import Folder
from registry import register_resource_class, get_resource_class
from ui import UI, ui_path
from user import UserFolder
from utils import crypt_password
from website import WebSite


# itools source and target languages
config = get_abspath('setup.conf')
config = ConfigFile(config)
itools_source_language = config.get_value('source_language')
itools_target_languages = config.get_value('target_languages')


# Force email to send UTF-8 mails in plain text
add_charset('utf-8', QP, None, 'utf-8')
add_codec('utf-8', 'utf_8')



class CtrlView(BaseView):

    access = True
    query_schema = {'name': String}


    def GET(self, resource, context):
        context.response.set_header('content-type', 'text/plain')
        name = context.query['name']

        # Read-Only
        if name == 'read-only':
            database = context.database
            return 'no' if isinstance(database, RWDatabase) else 'yes'

        return '?'



class Root(WebSite):

    class_id = 'iKaaro'
    class_title = MSG(u'iKaaro')
    class_icon16 = 'icons/16x16/root.png'
    class_icon48 = 'icons/48x48/root.png'
    class_control_panel = ['browse_users', 'add_user', 'edit_virtual_hosts',
                           'edit_security_policy', 'edit_languages',
                           'edit_contact_options']


    __fixed_handlers__ = ['users', 'ui']


    __roles__ = [
        {'name': 'admins', 'title': MSG(u'Admin')}]


    @staticmethod
    def _make_resource(cls, folder, email, password):
        # The metadata
        metadata = cls.build_metadata(admins=('0',))
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
    # Traverse
    ########################################################################
    def _get_resource(self, name):
        if name == 'ui':
            ui = UI(ui_path)
            ui.database = self.metadata.database
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
            config = ConfigFile(str(config))
            source = config.get_value('source_language', default=source)
            target = config.get_value('target_languages', default=target)

        target = target.split()
        if source in target:
            target.remove(source)

        target.insert(0, source)
        return target


    ########################################################################
    # Search
    def search(self, query=None, **kw):
        catalog = get_context().database.catalog
        return catalog.search(query, **kw)


    #######################################################################
    # Web services
    #######################################################################
    _ctrl = CtrlView()




###########################################################################
# Register
###########################################################################
register_resource_class(Root)
