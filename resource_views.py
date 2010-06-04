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

# Import from the Standard Library
from datetime import datetime

# Import from itools
from itools.datatypes import DateTime, String, Unicode
from itools.gettext import MSG
from itools.http import Conflict, NotImplemented
from itools.i18n import get_language_name
from itools.uri import get_reference, get_uri_path
from itools.web import BaseView, STLForm, INFO, ERROR
from itools.xapian import PhraseQuery

# Import from ikaaro
from autoform import AutoForm, title_widget, description_widget, subject_widget
from autoform import timestamp_widget
from datatypes import CopyCookie
from exceptions import ConsistencyError
from folder_views import Folder_BrowseContent
import messages
from views import ContextMenu



class EditLanguageMenu(ContextMenu):

    title = MSG(u'Edit Language')

    def get_items(self):
        content_language = self.resource.get_content_language(self.context)

        site_root = self.resource.get_site_root()
        languages = site_root.get_property('website_languages')
        uri = self.context.uri
        return [
            {'title': get_language_name(x),
             'href': uri.replace(content_language=x),
             'class': 'nav-active' if (x == content_language) else None}
            for x in languages ]



class DBResource_Edit(AutoForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit')
    icon = 'metadata.png'
    context_menus = [EditLanguageMenu()]

    schema = {
        'title': Unicode,
        'description': Unicode,
        'subject': Unicode,
        'timestamp': DateTime(readonly=True)}
    widgets = [
        timestamp_widget, title_widget, description_widget, subject_widget]


    def get_value(self, resource, context, name, datatype):
        if name == 'timestamp':
            return datetime.now()
        language = resource.get_content_language(context)
        return resource.get_property(name, language=language)


    def check_edit_conflict(self, resource, context, form):
        context.edit_conflict = False

        timestamp = form['timestamp']
        if timestamp is None:
            context.message = messages.MSG_EDIT_CONFLICT
            context.edit_conflict = True
            return

        root = context.root
        results = root.search(abspath=str(resource.get_canonical_path()))
        brain = results.get_documents()[0]
        mtime = brain.mtime
        if mtime is not None and timestamp < mtime:
            # Conflict unless we are overwriting our own work
            last_author = resource.get_last_author()
            if last_author != context.user.name:
                user = root.get_user_title(last_author)
                context.message = messages.MSG_EDIT_CONFLICT2(user=user)
                context.edit_conflict = True


    def action(self, resource, context, form):
        # Check edit conflict
        self.check_edit_conflict(resource, context, form)
        if context.edit_conflict:
            return

        # Save changes
        title = form['title']
        description = form['description']
        subject = form['subject']
        language = resource.get_content_language(context)
        resource.set_property('title', title, language=language)
        resource.set_property('description', description, language=language)
        resource.set_property('subject', subject, language=language)
        # Ok
        context.message = messages.MSG_CHANGES_SAVED



class DBResource_Backlinks(Folder_BrowseContent):
    """Backlinks are the list of resources pointing to this resource.  This
    view answers the question "where is this resource used?" You'll see all
    WebPages (for example) referencing it.  If the list is empty, you can
    consider it is "orphan".
    """

    access = 'is_allowed_to_view'
    title = MSG(u"Backlinks")
    icon = 'rename.png'

    search_template = None
    search_schema = {}

    # Skip AddResourceMenu
    context_menus = []

    def get_table_columns(self, resource, context):
        cols = Folder_BrowseContent.get_table_columns(self, resource, context)
        return [ col for col in cols if col[0] != 'checkbox' ]


    def get_items(self, resource, context):
        query = PhraseQuery('links', str(resource.get_canonical_path()))
        return context.root.search(query)


    table_actions = []



###########################################################################
# Views / Login, Logout
###########################################################################

class LoginView(STLForm):

    access = True
    title = MSG(u'Login')
    template = '/ui/base/login.xml'
    schema = {
        'username': Unicode(mandatory=True),
        'password': String(mandatory=True)}
    meta = [('robots', 'noindex, follow', None)]


    def action(self, resource, context, form):
        email = form['username'].strip()
        password = form['password']

        # Check the user exists
        root = context.root
        user = root.get_user_from_login(email)
        if user is None:
            message = ERROR(u'The user "{username}" does not exist.',
                            username=email)
            context.message = message
            return

        # Check the password is right
        if not user.authenticate(password, clear=True):
            context.message = ERROR(u'The password is wrong.')
            return

        # Set cookie
        user.set_auth_cookie(context, password)

        # Set context
        context.user = user

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
        # Log-out
        context.del_cookie('__ac')
        context.user = None

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


