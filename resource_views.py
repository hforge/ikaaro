# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2007-2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2008 Matthieu France <matthieu@itaapy.com>
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

# Import from itools
from itools.core import merge_dicts
from itools.database import OrQuery, PhraseQuery
from itools.datatypes import Boolean, Email, Integer, String
from itools.gettext import MSG
from itools.stl import stl
from itools.uri import get_reference, get_uri_path
from itools.web import BaseView, STLForm, INFO, ERROR
from itools.web import Conflict, NotImplemented

# Import from ikaaro
from datatypes import CopyCookie
from exceptions import ConsistencyError
from folder_views import Folder_BrowseContent



class DBResource_Links(Folder_BrowseContent):
    """Links are the list of resources used by this resource."""

    access = 'is_allowed_to_view'
    title = MSG(u"Links")
    icon = 'rename.png'

    query_schema = merge_dicts(Folder_BrowseContent.query_schema,
                               batch_size=Integer(default=0))

    search_template = None
    search_schema = {}

    def get_table_columns(self, resource, context):
        cols = Folder_BrowseContent.get_table_columns(self, resource, context)
        return [ col for col in cols if col[0] != 'checkbox' ]


    def get_items(self, resource, context):
        links = resource.get_links()
        if type(links) is list: # TODO 'get_links' must return <set>
            links = set(links)
        query = OrQuery(*[ PhraseQuery('abspath', link) for link in links ])
        return context.root.search(query)


    table_actions = []



class DBResource_Backlinks(DBResource_Links):
    """Backlinks are the list of resources pointing to this resource. This
    view answers the question "where is this resource used?" You'll see all
    WebPages (for example) referencing it. If the list is empty, you can
    consider it is "orphan".
    """

    title = MSG(u"Backlinks")

    def get_items(self, resource, context):
        query = PhraseQuery('links', str(resource.get_abspath()))
        return context.root.search(query)



###########################################################################
# Views / Login, Logout
###########################################################################
class LoginView(STLForm):

    access = True
    title = MSG(u'Login')
    template = '/ui/base/login.xml'
    query_schema = {'username': String}
    schema = {
        'username': String(mandatory=True),
        'password': String,
        'no_password': Boolean}
    meta = [('robots', 'noindex, follow', None)]


    def get_value(self, resource, context, name, datatype):
        if name == 'username':
            return context.query['username']
        proxy = super(LoginView, self)
        return proxy.get_value(resource, context, name, datatype)


    def get_namespace(self, resource, context):
        namespace = super(LoginView, self).get_namespace(resource, context)

        user = context.user
        register = context.site_root.is_allowed_to_register(user, resource)
        namespace['register'] = register

        return namespace


    def action(self, resource, context, form):
        # Get the user
        email = form['username'].strip()
        user = context.site_root.get_user_from_login(email)

        # Case 1: Forgotten password
        if form['no_password']:
            if not Email.is_valid(email):
                message = u'The given username is not an email address.'
                context.message = ERROR(message)
                return

            email = user.get_property('email')
            user.send_forgotten_password(context, email)
            path = '/ui/website/forgotten_password.xml'
            handler = resource.get_resource(path)
            return stl(handler)

        # Case 2: Login
        password = form['password']
        if user is None or not user.authenticate(password, clear=True):
            context.message = ERROR(u'The email or the password is incorrect.')
            return

        context.login(user)

        # Come back
        referrer = context.get_referrer()
        if referrer is None:
            goto = get_reference('./')
        else:
            path = get_uri_path(referrer)
            if path.endswith(';login'):
                goto = get_reference('./')
            else:
                goto = referrer

        return context.come_back(INFO(u"Welcome!"), goto)



class LogoutView(BaseView):
    """Logs out of the application.
    """

    access = True


    def GET(self, resource, context):
        context.logout()

        message = INFO(u'You Are Now Logged out.')
        return context.come_back(message, goto='./')



###########################################################################
# Views / HTTP, WebDAV
###########################################################################

class Put_View(BaseView):

    access = 'is_allowed_to_put'


    def PUT(self, resource, context):
        range = context.get_header('content-range')
        if range:
            raise NotImplemented

        # Save the data
        body = context.get_form_value('body')
        resource.handler.load_state_from_string(body)
        context.database.change_resource(resource)



class Delete_View(BaseView):

    access = 'is_allowed_to_remove'


    def DELETE(self, resource, context):
        name = resource.name
        parent = resource.parent
        try:
            parent.del_resource(name)
        except ConsistencyError:
            raise Conflict

        # Clean the copy cookie if needed
        cut, paths = context.get_cookie('ikaaro_cp', datatype=CopyCookie)
        # Clean cookie
        if str(resource.get_abspath()) in paths:
            context.del_cookie('ikaaro_cp')
            paths = []
