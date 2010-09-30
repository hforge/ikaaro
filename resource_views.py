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
from itools.datatypes import Boolean, DateTime, Email, Integer, String, Unicode
from itools.gettext import MSG
from itools.http import Conflict, NotImplemented
from itools.i18n import get_language_name
from itools.stl import stl
from itools.uri import get_reference, get_uri_path, Reference
from itools.web import BaseView, STLForm, INFO, ERROR
from itools.database import OrQuery, PhraseQuery

# Import from ikaaro
from autoform import AutoForm, title_widget, description_widget, subject_widget
from autoform import timestamp_widget
from datatypes import CopyCookie, Multilingual
from exceptions import ConsistencyError
from folder_views import Folder_BrowseContent
from views import ContextMenu
import messages



class EditLanguageMenu(ContextMenu):

    title = MSG(u'Configuration')
    template = '/ui/generic/edit_language_menu.xml'
    view = None
    submit_value = MSG(u'Update')
    submit_class = 'button-ok'

    def action(self):
        uri = self.context.uri
        return Reference(uri.scheme, uri.authority, uri.path, {}, None)


    def get_fields(self):
        context = self.context
        resource = self.resource
        view = self.view

        widgets = view._get_widgets(resource, context)
        # Build widgets list
        fields, to_keep = view._get_query_fields(resource, context)

        return [ {'name': widget.name,
                  'title': getattr(widget, 'title', 'name'),
                  'selected': widget.name in fields}
                 for widget in widgets if widget.name not in to_keep ]


    def fields(self):
        items = self.get_fields()
        # Defaults
        for item in items:
            for name in ['class', 'src', 'items']:
                item.setdefault(name, None)

        return items


    def get_items(self):
        site_root = self.resource.get_site_root()
        languages = site_root.get_property('website_languages')
        edit_languages = self.resource.get_edit_languages(self.context)
        uri = self.context.uri
        return [
            {'title': get_language_name(x),
             'name': x,
             'selected': x in edit_languages}
            for x in languages ]



    def get_hidden_fields(self):
        return self.view._get_query_to_keep(self.resource, self.context)


    def hidden_fields(self):
        return self.get_hidden_fields()



class DBResource_Edit(AutoForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit')
    icon = 'metadata.png'
    context_menus = []

    schema = {
        'title': Multilingual,
        'description': Multilingual(hidden_by_default=True),
        'subject': Multilingual(hidden_by_default=True),
        'timestamp': DateTime(readonly=True)}
    widgets = [
        timestamp_widget, title_widget, description_widget, subject_widget]


    def get_context_menus(self):
        context_menus = self.context_menus[:] # copy
        context_menus.append(EditLanguageMenu(view=self))
        return context_menus


    # XXX method name sucks
    def _get_query_to_keep(self, resource, context):
        """Return a list of dict {'name': name, 'value': value}"""
        return []


    def _get_query_fields(self, resource, context):
        """Return query fields and readonly or mandatory fields
        """
        schema = self._get_schema(resource, context)
        default = set()
        to_keep = set()

        for key, datatype in schema.iteritems():
            if getattr(datatype, 'hidden_by_default', False):
                continue
            # Keep readonly and mandatory widgets
            if getattr(datatype, 'mandatory', False):
                to_keep.add(key)
            if getattr(datatype, 'readonly', False):
                to_keep.add(key)
            default.add(key)
        fields = context.get_query_value('fields', type=String(multiple=True),
                                         default=default)
        return set(fields), to_keep


    def _get_schema(self, resource, context):
        """Return schema witout any modification
           Method to be overriden by sub-classes.
        """
        return self.schema


    def get_schema(self, resource, context):
        """Return reduced schema
           i.e. schema without 'hidden by default' datatypes.
        """
        base_schema = self._get_schema(resource, context)
        fields, to_keep = self._get_query_fields(resource, context)
        schema = {}
        for key in fields | to_keep:
            schema[key] = base_schema[key]

        return schema


    def _get_widgets(self, resource, context):
        """Return widgets witout any modification
           Method to be overriden by sub-classes.
        """
        return self.widgets


    def get_widgets(self, resource, context):
        """Return reduced widgets
           i.e. skip hide by default widgets.
        """
        base_widgets = self._get_widgets(resource, context)
        fields, to_keep = self._get_query_fields(resource, context)

        # Reduce widgets
        return [ widget for widget in base_widgets
                 if widget.name in fields or widget.name in to_keep ]


    def get_value(self, resource, context, name, datatype):
        if name == 'timestamp':
            return context.timestamp

        if not getattr(datatype, 'multilingual', False):
            return resource.get_property(name)

        value = {}
        for language in resource.get_edit_languages(context):
            value[language] = resource.get_property(name, language=language)
        return value


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
            last_author = resource.get_property('last_author')
            if last_author != context.user.name:
                user = root.get_user_title(last_author)
                context.message = messages.MSG_EDIT_CONFLICT2(user=user)
                context.edit_conflict = True


    def action(self, resource, context, form):
        # Check edit conflict
        self.check_edit_conflict(resource, context, form)
        if context.edit_conflict:
            return

        # Get submit field names
        schema = self._get_schema(resource, context)
        fields, to_keep = self._get_query_fields(resource, context)

        # Save changes
        language = resource.get_edit_languages(context)[0]
        for key in fields | to_keep:
            datatype = schema[key]
            if getattr(datatype, 'readonly', False):
                continue
            if self.set_value(resource, context, key, form):
                return
        # Ok
        context.message = messages.MSG_CHANGES_SAVED


    def set_value(self, resource, context, name, form):
        """Return True if an error occurs otherwise False

           If an error occurs, the context.message must be an ERROR instance.
        """
        value = form[name]
        if type(value) is dict:
            for language, data in value.iteritems():
                resource.set_property(name, data, language=language)
        else:
            resource.set_property(name, value)
        return False



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
        links = list(set(links))
        query = OrQuery(*[ PhraseQuery('abspath', link)
                           for link in links ])
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
        query = PhraseQuery('links', str(resource.get_canonical_path()))
        return context.root.search(query)



###########################################################################
# Views / Login, Logout
###########################################################################

class LoginView(STLForm):

    access = True
    title = MSG(u'Login')
    template = '/ui/base/login.xml'
    schema = {
        'username': String(mandatory=True),
        'password': String,
        'no_password': Boolean}
    meta = [('robots', 'noindex, follow', None)]


    def get_namespace(self, resource, context):
        namespace = super(LoginView, self).get_namespace(resource, context)
        namespace['register'] = context.site_root.is_allowed_to_register()
        return namespace


    def _register(self, resource, context, email):
        site_root = context.site_root
        # Add the user
        users = site_root.get_resource('users')
        user = users.set_user(email, None)
        # Set the role
        default_role = site_root.class_roles[0]
        site_root.set_user_role(user.name, default_role)

        # Send confirmation email
        user.send_confirmation(context, email)

        # Bring the user to the login form
        message = MSG(
            u"An email has been sent to you, to finish the registration "
            u"process follow the instructions detailed in it.")
        return message.gettext().encode('utf-8')


    def action(self, resource, context, form):
        # Get the user
        email = form['username'].strip()
        user = context.root.get_user_from_login(email)

        if form['no_password']:
            if not Email.is_valid(email):
                message = u'The given username is not an email address.'
                context.message = ERROR(message)
                return

            # Case 1: Register
            if user is None:
                if context.site_root.is_allowed_to_register():
                    return self._register(resource, context, email)
                # FIXME This message does not protect privacy
                error = u"You don't have an account, contact the site admin."
                context.message = ERROR(error)
                return

            # Case 2: Forgotten password
            email = user.get_property('email')
            user.send_forgotten_password(context, email)
            path = '/ui/website/forgotten_password.xml'
            handler = resource.get_resource(path)
            return stl(handler)

        # Case 3: Login
        password = form['password']
        if user is None or not user.authenticate(password, clear=True):
            context.message = ERROR(u'The email or the password is incorrect.')
            return

        # Set cookie & context
        user.set_auth_cookie(context, password)
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


