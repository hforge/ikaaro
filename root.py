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
from itools.datatypes import String
from itools.gettext import MSG
from itools.handlers import RWDatabase
from itools.http import get_context
from itools.stl import stl
from itools.web import BaseView

# Import from ikaaro
from folder import Folder
from registry import register_resource_class, get_resource_class
from user import UserFolder
from utils import crypt_password
from website import WebSite


# Force email to send UTF-8 mails in plain text
add_charset('utf-8', QP, None, 'utf-8')
add_codec('utf-8', 'utf_8')



class CtrlView(BaseView):

    access = True
    query_schema = {'name': String}


    def http_get(self, resource, context):
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


    def _get_names(self):
        return [ x for x in Folder._get_names(self) if x ]


    def get_document_types(self):
        return WebSite.get_document_types(self) + [WebSite]


    #######################################################################
    # Web services
    #######################################################################
    _ctrl = CtrlView()




###########################################################################
# Register
###########################################################################
register_resource_class(Root)
