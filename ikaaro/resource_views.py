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
import json

from itools.core import guess_extension, merge_dicts, is_prototype
from itools.database import OrQuery, PhraseQuery
from itools.datatypes import Boolean, Integer, String
from itools.gettext import MSG
from itools.stl import stl
from itools.uri import get_reference, get_uri_path
from itools.web import get_context, NewJSONEncoder
from itools.web import BaseView, STLView, INFO, ERROR
from itools.web import NotFound
from itools.web.exceptions import FormError

# Import from ikaaro
from ikaaro.views.folder_views import Folder_BrowseContent
from ikaaro.fields import Boolean_Field, Field
from ikaaro.buttons import Button
from ikaaro.widgets import FileWidget
from ikaaro.datatypes import FileDataType

# Import from ikaaro
from .autoform import AutoForm
from .buttons import Remove_Button
from .emails import send_email
from .exceptions import ConsistencyError
from .messages import MSG_LOGIN_WRONG_NAME_OR_PASSWORD



class DBResource_Remove(AutoForm):

    access = 'is_allowed_to_remove'
    title = MSG('Remove')

    actions = [Remove_Button]

    def action_remove(self, resource, context, form):
        container = resource.parent

        try:
            container.del_resource(resource.name)
        except ConsistencyError:
            err = (
                'Referenced resource cannot be removed, check the <a href=";backlinks">backlinks</a>.')
            context.message = ERROR(err, format='html')
            return

        # Ok
        message = MSG('Resource removed')
        return context.come_back(message, goto=str(container.abspath))



class DBResource_GetFile(BaseView):

    access = 'is_allowed_to_view'

    query_schema = {'name': String(),
                    'language': String()}
    field_name = None


    def get_field_name(self, context=None):
        if self.field_name:
            return self.field_name
        if context is None:
            context = get_context()
        return context.query['name']


    def get_handler(self, resource, name, language=None):
        return resource.get_value(name, language=language)


    def get_mtime(self, resource):
        language = self.context.get_query_value('language')
        field_name = self.get_field_name()
        handler = self.get_handler(resource, field_name, language)
        if handler is None:
            raise NotFound
        return handler.get_mtime()


    def get_content_type(self, handler):
        mimetype = get_context().get_query_value('mimetype')
        if mimetype:
            return mimetype
        return handler.get_mimetype()


    def get_filename(self, handler, field_name, resource):
        mimetype = self.get_content_type(handler)
        extension = guess_extension(mimetype)
        language = self.context.get_query_value('language') or ''
        if language:
            language = '.%s' % language
        return '%s.%s%s%s' % (resource.name, field_name, language, extension)


    def GET(self, resource, context):
        language = context.query['language']
        field_name = self.get_field_name(context)
        handler = self.get_handler(resource, field_name, language)
        # Content-Type
        content_type = self.get_content_type(handler)
        context.set_content_type(content_type)
        # Content-Disposition
        disposition = 'attachment'
        filename = self.get_filename(handler, field_name, resource)
        context.set_content_disposition(disposition, filename)
        # Ok
        return handler.to_str()



class DBResource_GetImage(DBResource_GetFile):

    query_schema = {
        'name': String(),
        'width': Integer(),
        'height': Integer(),
        'language': String(),
        'fit': Boolean(default=False),
        'lossy': Boolean(default=False)}


    def GET(self, resource, context):
        field_name = self.get_field_name(context)
        language = context.query['language']
        handler = self.get_handler(resource, field_name, language)

        image_width, image_height = handler.get_size()
        fit = context.query['fit']
        lossy = context.query['lossy']
        width = context.query['width'] or image_width
        height = context.query['height'] or image_height

        format = 'jpeg'
        if lossy is False:
            format = handler.get_mimetype().split('/')[1]
        data, format = handler.get_thumbnail(width, height, format, fit)
        if data is None:
            default = context.get_template('/ui/ikaaro/icons/48x48/image.png')
            data = default.to_str()
            format = 'png'

        # Headers
        context.set_content_type('image/%s' % format)

        # Ok
        return data



class DBResource_Links(Folder_BrowseContent):
    """Links are the list of resources used by this resource."""

    access = 'is_admin'
    title = MSG("Links")
    icon = 'rename.png'

    query_schema = merge_dicts(Folder_BrowseContent.query_schema,
                               batch_size=Integer(default=0))

    search_schema = {}
    search_widgets = []

    table_actions = []

    def get_table_columns(self, resource, context):
        proxy = super(DBResource_Links, self)
        cols = proxy.get_table_columns(resource, context)
        return [ x for x in cols if x[0] != 'checkbox' ]


    def get_items(self, resource, context):
        links = resource.get_links()
        query = OrQuery(*[ PhraseQuery('abspath', link) for link in links ])
        return context.database.search(query)



class DBResource_Backlinks(DBResource_Links):
    """Backlinks are the list of resources pointing to this resource. This
    view answers the question "where is this resource used?" You'll see all
    WebPages (for example) referencing it. If the list is empty, you can
    consider it is "orphan".
    """

    title = MSG("Backlinks")

    def get_items(self, resource, context):
        return context.search(links=str(resource.abspath))



###########################################################################
# Views / Login, Logout
###########################################################################
class LoginView(STLView):

    access = True
    title = MSG('Login')
    template = '/ui/ikaaro/base/login.xml'
    meta = [('robots', 'noindex, follow', None)]

    query_schema = {
        'loginname': String(),
        'no_password': Boolean()}
    schema = {
        'loginname': String(mandatory=True),
        'password': String(),
        'no_password': Boolean()}

    def GET(self, resource, context):
        if context.user:
            msg = MSG('You are already connected')
            goto = str(context.user.abspath)
            return context.come_back(msg, goto)
        return super(LoginView, self).GET(resource, context)


    def POST(self, resource, context):
        if context.status == 401:
            # Don't submit login with data from another form
            return self.GET
        return super(LoginView, self).POST(resource, context)


    def get_value(self, resource, context, name, datatype):
        if name == 'loginname':
            return context.query['loginname']
        proxy = super(LoginView, self)
        return proxy.get_value(resource, context, name, datatype)


    def get_namespace(self, resource, context):
        namespace = super(LoginView, self).get_namespace(resource, context)
        namespace['no_password'] = context.query['no_password']
        # Register
        user = context.user
        register = context.root.is_allowed_to_register(user, resource)
        namespace['register'] = register
        # Login name
        cls = context.database.get_resource_class('user')
        field = cls.get_field(cls.login_name_property)
        namespace['login_name_title'] = field.title
        # Ok
        return namespace


    def action(self, resource, context, form):
        # Get the user
        loginname = form['loginname'].strip()
        user = context.root.get_user_from_login(loginname)

        # Case 1: Forgotten password
        if form['no_password']:
            # 1.1 Send email
            if user:
                email = user.get_value('email')
                if user.get_value('user_state') == 'inactive':
                    email_id = None # TODO
                else:
                    user.update_pending_key()
                    email_id = 'forgotten-password-ask-for-confirmation'
            else:
                email_id = None # TODO Which is the email address?

            if email_id:
                send_email(email_id, context, email, user=user)

            # 1.2 Show message (we show the same message even if the user
            # does not exist, because privacy wins over usability)
            path = '/ui/ikaaro/website/forgotten_password.xml'
            handler = context.get_template(path)
            return stl(handler)

        # Case 2: Login
        if user is None:
            context.message = MSG_LOGIN_WRONG_NAME_OR_PASSWORD
            return

        error = user._login(form['password'], context)
        if error:
            context.message = error
            return

        return self.get_goto(user)


    def get_goto(self, user):
        context = self.context

        # Check if user account is completed
        for name, field in user.get_fields():
            if field.required and user.get_value(name) is None:
                msg = MSG('You must complete your account informations')
                goto = '/users/%s/;edit_account' % user.name
                return context.come_back(msg, goto)

        # Come back
        referrer = context.get_referrer()
        if referrer is None:
            goto = get_reference('./')
        else:
            path = get_uri_path(referrer)
            if path.endswith(';login') or path.endswith(';register'):
                goto = get_reference('./')
            else:
                goto = referrer

        return context.come_back(INFO("Welcome!"), goto)



class LogoutView(BaseView):
    """Logs out of the application.
    """

    access = True


    def GET(self, resource, context):
        context.logout()

        message = INFO('You Are Now Logged out.')
        return context.come_back(message, goto='./')



class AutoJSONResourceExport(AutoForm):

    access = "is_admin"
    title = MSG("Exporter au format JSON")

    def _get_datatype(self, resource, context, name):
        field = self.get_field(resource, name)
        return field.get_datatype()


    def _get_schema(self, resource, context):
        schema = {}
        # Add schema from the resource
        for name in self.get_fields():
            datatype = self._get_datatype(resource, context, name)
            # Standard case
            schema[name] = datatype

        return schema

    def get_schema(self, resource, context):
        """Return reduced schema
           i.e. schema without 'hidden by default' datatypes.
        """
        base_schema = self._get_schema(resource, context)
        return base_schema


    def _get_widget(self, resource, context, name):
        field = self.get_field(resource, name)
        widget = field.get_widget(name)
        widget = widget(datatype=field.datatype)
        return widget


    def _get_widgets(self, resource, context):
        widgets = []
        for name in self.get_fields():
            widget = self._get_widget(resource, context, name)
            widget_css = widget.css or ''
            widget.css = widget_css + ' form-control'
            widgets.append(widget)
        return widgets


    def get_widgets(self, resource, context):
        """Return reduced widgets
           i.e. skip hide by default widgets.
        """
        base_widgets = self._get_widgets(resource, context)
        return base_widgets

    def get_fields(self):
        resource = self.resource
        json_export_allowed_fields = resource.get_exportable_fields()
        for name, field in json_export_allowed_fields:
            if not is_prototype(field, Field):
                field = resource.get_field(name)
            if not field:
                continue
            # Access control
            if field.access('write', resource):
                yield name


    def get_field(self, resource, name):
        resource_field = resource.get_field(name)
        field = Boolean_Field(
            title=MSG("Exporter le champs '{title}' ?").gettext(
                title=resource_field.title
            ),
            default=True
        )
        return field


    def action(self, resource, context, form):
        fields = [key for key, value in form.items() if value]
        json_export = resource.export_as_json(context, only_self=True, exported_fields=fields)
        json_export["export_type"] = "self-export"
        context.set_content_type("application/json")
        file_name = "config_export_{title}.json".format(
            title=resource.get_title()
        )
        context.set_content_disposition("attachment", file_name)
        return json.dumps(json_export, cls=NewJSONEncoder)


class AutoJSONResourcesImport(AutoForm):

    access = "is_admin"
    title = MSG("Importer au format JSON")

    schema = {
        "file": FileDataType(mandatory=True),}
    widgets = [
        FileWidget("file")
    ]

    actions = [
        Button(access='is_admin', css='btn btn-primary', title=MSG('Upload'))]


    def _get_form(self, resource, context):
        form = super(AutoJSONResourcesImport, self)._get_form(resource, context)
        # Check the mimetype
        filename, mimetype, body = form['file']
        if mimetype != "application/json":
            raise FormError()
        filename, mimetype, json_raw = form.pop("file")
        json_content = json.loads(json_raw)
        form["json_import"] = json_content
        export_type = json_content["export_type"]
        if export_type == "child-export":
            for json_item in json_content["items"]:
                resource.import_children_as_json(
                    context,
                    json_item,
                    dry_run=True
                )
        elif export_type == "self-export":
            # Check that imported json is the right resource
            if resource.class_id != json_content["class_id"]:
                raise FormError(
                    ERROR("Le type de ressource que vous essayez d'importer ne "
                          "correspond pas au type de la ressource actuelle")
                )
            if resource.class_version != json_content["class_version"]:
                raise FormError(
                    ERROR("La version de la ressource que vous essayez d'importer "
                          "ne correspond pas à la version de la ressource actuelle")
                )
            resource.update_metadata_from_dict(json_content["fields"], dry_run=True)
        return form

    action_goto = "."
    def action(self, resource, context, form):
        json_content = form["json_import"]
        export_type = json_content["export_type"]
        if export_type == "child-export":
            for json_item in json_content["items"]:
                resource.import_children_as_json(context, json_item)
        elif export_type == "self-export":
            # Check that imported json is the right resource
            if resource.class_id != json_content["class_id"]:
                raise FormError(
                    ERROR("Le type de ressource que vous essayez d'importer ne "
                          "correspond pas au type de la ressource actuelle")
                )
            if resource.class_version != json_content["class_version"]:
                raise FormError(
                    ERROR("La version de la ressource que vous essayez d'importer "
                          "ne correspond pas à la version de la ressource actuelle")
                )
            resource.update_metadata_from_dict(json_content["fields"])
        return context.come_back(
            MSG("Les ressources ont bien été importées"),
            goto=self.action_goto
        )

