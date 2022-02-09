# -*- coding: UTF-8 -*-
# Copyright (C) 2011 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from itools.core import proto_lazy_property, is_prototype
from itools.datatypes import DateTime, String, Time, Unicode, URI
from itools.gettext import MSG
from itools.handlers import checkid
from itools.web import get_context, ERROR, FormError

# Import from ikaaro
from .autoform import AutoForm
from .datatypes import BirthDate
from .datatypes import Days, Months, Years
from .buttons import Button
from .fields import Field
from . import messages
from .widgets import HiddenWidget, ReadOnlyWidget




class AutoAdd(AutoForm):

    access = 'is_allowed_to_add'

    actions = [Button(access=True, css='btn btn-primary', title=MSG('Add'))]
    action_goto = None
    goto_view = None
    goto_parent_view = None # DEPRECATED -> use action_goto
    msg_new_resource = messages.MSG_NEW_RESOURCE


    # Fields
    fields = []
    def get_fields(self):
        cls = self._resource_class
        for name in self.fields:
            field = self.get_field(name)
            if not is_prototype(field, Field):
                field = cls.get_field(name)

            if not field:
                continue

            # Access control
            if field.access('write', cls):
                yield name


    def get_field(self, name):
        cls = self._resource_class
        field = getattr(self, name, None)
        if field is None or not is_prototype(field, Field):
            field = cls.get_field(name)
        return field



    #######################################################################
    # GET
    #######################################################################
    @proto_lazy_property
    def _resource_class(self):
        context = self.context

        class_id = context.query.get('type')
        if not class_id:
            return None
        return context.database.get_resource_class(class_id)


    def get_title(self, context):
        if self.title is not None:
            return self.title

        cls = self._resource_class
        if cls:
            class_title = cls.class_title.gettext()
            title = MSG('Add {class_title}')
            return title.gettext(class_title=class_title)

        return MSG('Add resource').gettext()


    def _get_datatype(self, resource, context, name):
        cls = self._resource_class

        field = self.get_field(name)

        field = field(resource=cls) # bind
        return field.get_datatype()


    def get_query_schema(self):
        context = get_context()
        resource = context.resource

        schema = self.get_schema(resource, context)
        for name, datatype in schema.items():
            if getattr(datatype, 'mandatory', False) is True:
                schema[name] = datatype(mandatory=False)

        schema['type'] = String
        return schema


    def get_schema(self, resource, context):
        schema = {
            'cls_description': Unicode,
            'referrer': URI}
        for name in self.get_fields():
            datatype = self._get_datatype(resource, context, name)
            if datatype is None:
                continue
            # Special case: datetime
            elif issubclass(datatype, DateTime):
                schema['%s_time' % name] = Time
            # Special case: birthdate
            elif issubclass(datatype, BirthDate):
                schema['%s_day' % name] = Days
                schema['%s_month' % name] = Months
                schema['%s_year' % name] = Years

            # Standard case
            schema[name] = datatype

        return schema


    def _get_widget(self, resource, context, name):
        field = self.get_field(name)
        return field.get_widget(name)


    def get_widgets(self, resource, context):
        widgets = [
            ReadOnlyWidget('cls_description'),
            HiddenWidget('referrer')]
        for name in self.get_fields():
            widget = self._get_widget(resource, context, name)
            widgets.append(widget)

        return widgets


    def get_value(self, resource, context, name, datatype):
        if name == 'cls_description':
            # View cls_description
            value = getattr(self, name, None)
            if value is not None:
                return value.gettext() if value else ''
            # Resource cls_description
            cls = self._resource_class
            value = cls.class_description
            return value.gettext() if value else ''
        elif name == 'referrer':
            referrer = context.query.get('referrer')
            return referrer or context.get_referrer()
        value = context.query.get(name)
        if value is None:
            proxy = super(AutoAdd, self)
            return proxy.get_value(resource, context, name, datatype)

        if getattr(datatype, 'multilingual', False):
            for language in resource.get_edit_languages(context):
                value.setdefault(language, '')

        return value



    #######################################################################
    # POST
    #######################################################################
    def get_container(self, resource, context, form):
        # Container
        container = resource
        path = str(container.abspath)

        # Access control
        class_id = context.query['type']
        root = context.root
        if not root.has_permission(context.user, 'add', container, class_id):
            path = '/' if path == '.' else '/%s/' % path
            msg = ERROR('Adding resources to {path} is not allowed.')
            raise FormError(msg.gettext(path=path))

        # Ok
        return container


    automatic_resource_name = False
    def get_new_resource_name(self, form):
        if self.automatic_resource_name:
            return form['container'].make_resource_name()

        # If the name is not explicitly given, use the title
        name = form.get('name', '').strip()
        if name:
            return name

        context = get_context()
        lang = self.resource.get_edit_languages(context)[0]
        return form['title'][lang]


    def _get_form(self, resource, context):
        form = super(AutoAdd, self)._get_form(resource, context)

        # 1. The container
        container = self.get_container(resource, context, form)
        form['container'] = container

        # 2. The name
        name = self.get_new_resource_name(form)
        if not name:
            raise FormError(messages.MSG_NAME_MISSING)
        try:
            name = checkid(name)
        except UnicodeEncodeError:
            name = None
        if name is None:
            raise FormError(messages.MSG_BAD_NAME)

        # Check the name is free
        if container.get_resource(name, soft=True) is not None:
            raise FormError(messages.MSG_NAME_CLASH)
        form['name'] = name

        # Ok
        return form


    def set_value(self, resource, context, name, form):
        """Return True if an error occurs otherwise False. If an error
        occurs, the context.message must be an ERROR instance.
        """
        if name.endswith(('_time', '_year', '_day', '_month')):
            return False

        if resource.get_field(name) is None:
            return False

        value = form[name]
        if type(value) is dict:
            for language, data in value.items():
                resource.set_value(name, data, language=language)
        else:
            resource.set_value(name, value)
        return False


    def init_new_resource(self, resource, context, form):
        child = form['child']

        schema = self.get_schema(resource, context)
        for name in self.get_fields():
            datatype = schema.get(name)
            if not datatype:
                continue
            readonly = getattr(datatype, 'readonly', False)
            persistent = getattr(datatype, 'persistent', True)
            if persistent and not readonly:
                if self.set_value(child, context, name, form):
                    return None
        return child


    def make_new_resource(self, resource, context, form):
        """Returns None if there is an error, otherwise return the new
        resource.
        """
        # 1. Make the resource
        container = form['container']
        cls = self._resource_class
        form['child'] = container.make_resource(form['name'], cls)
        # 2. Set properties
        return self.init_new_resource(resource, context, form)


    def action(self, resource, context, form):
        child = self.make_new_resource(resource, context, form)
        if child is None:
            return

        # Ok
        if self.action_goto:
            # Get same redirection from x/y/z/;edit and x/y/z and x/y/z/
            goto = self.action_goto
            if goto[0] not in ('/', 'http://'):
                path = str(context.uri.path)
                if ('/;' not in path and '/?' not in path
                        and not path.endswith('/')):
                    goto = '%s/%s' % (resource.name, goto)
            return context.come_back(self.msg_new_resource, goto=goto)
        # goto_parent_view # Deprecated : To replace by action_goto
        goto = str(child.abspath)
        if self.goto_parent_view:
            goto = './;%s' % self.goto_parent_view
        # goto_view (from Child)
        elif self.goto_view:
            goto = '%s/;%s' % (child.abspath, self.goto_view)
        return context.come_back(self.msg_new_resource, goto=goto)
