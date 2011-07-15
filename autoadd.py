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
from itools.datatypes import DateTime, Time, String, Unicode, URI
from itools.gettext import MSG
from itools.handlers import checkid
from itools.web import get_context, ERROR, FormError

# Import from ikaaro
from autoform import AutoForm, HiddenWidget, ReadOnlyWidget
from autoform import get_default_widget, location_widget
from datatypes import BirthDate
from buttons import Button
from datatypes import ContainerPathDatatype, FileDataType
from enumerates import Days, Months, Years
import messages
from registry import get_resource_class



class AutoAdd(AutoForm):

    access = 'is_allowed_to_add'

    fields = ['title', 'location']
    actions = [Button(access=True, css='button-ok', title=MSG(u'Add'))]
    goto_view = None


    #######################################################################
    # GET
    #######################################################################
    def get_title(self, context):
        if self.title is not None:
            return self.title
        type = context.query['type']
        if not type:
            return MSG(u'Add resource').gettext()
        cls = get_resource_class(type)
        class_title = cls.class_title.gettext()
        title = MSG(u'Add {class_title}')
        return title.gettext(class_title=class_title)


    def _get_resource_schema(self, resource):
        class_id = get_context().query['type']
        return get_resource_class(class_id).class_schema


    def _get_datatype(self, resource, context, name):
        return self._get_resource_schema(resource)[name]


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
        for name in self.fields:
            # Special case: location
            if name == 'location':
                schema['path'] = ContainerPathDatatype
                schema['name'] = String(default='')
                continue

            datatype = self._get_datatype(resource, context, name)
            if datatype is None:
                continue

            # Special case: datetime
            if issubclass(datatype, DateTime):
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
        if name == 'location':
            return location_widget

        datatype = self._get_datatype(resource, context, name)
        title = getattr(datatype, 'title', name)
        widget = getattr(datatype, 'widget', None)
        if widget is None:
            widget = get_default_widget(datatype)
        return widget(name, title=title)


    def get_widgets(self, resource, context):
        widgets = [
            ReadOnlyWidget('cls_description'),
            HiddenWidget('referrer')]
        for name in self.fields:
            widget = self._get_widget(resource, context, name)
            widgets.append(widget)

        return widgets


    def get_value(self, resource, context, name, datatype):
        if name == 'cls_description':
            class_id = context.query['type']
            cls = get_resource_class(class_id)
            return cls.class_description.gettext()
        elif name == 'referrer':
            referrer = context.query.get('referrer')
            return referrer or context.get_referrer()
#       elif name == 'path':
#           return context.site_root.get_pathto(resource)
#       elif name in self.get_query_schema():
#           return context.query[name]

        if getattr(datatype, 'multilingual', False):
            value = {}
            for language in resource.get_edit_languages(context):
                value[language] = u'' # FIXME
            return value

        proxy = super(AutoAdd, self)
        return proxy.get_value(resource, context, name, datatype)


    #######################################################################
    # POST
    #######################################################################
    def get_container(self, resource, context, form):
        container = resource
        path = form['path']
        if path is not None:
            container = context.site_root.get_resource(path)
        ac = container.get_access_control()
        if not ac.is_allowed_to_add(context.user, container):
            path = '/' if path == '.' else '/%s/' % path
            msg = ERROR(u'Adding resources to {path} is not allowed.')
            raise FormError, msg.gettext(path=path)

        return container


    def get_new_resource_name(self, form):
        # If the name is not explicitly given, use the title
        name = form.get('name', '').strip()
        if name:
            return name

        lang = get_context().resource.get_site_root().get_default_language()
        return form['title'][lang]


    def _get_form(self, resource, context):
        form = super(AutoAdd, self)._get_form(resource, context)

        # 1. The container
        container = self.get_container(resource, context, form)
        form['container'] = container

        # 2. The name
        name = self.get_new_resource_name(form)
        if not name:
            raise FormError, messages.MSG_NAME_MISSING
        try:
            name = checkid(name)
        except UnicodeEncodeError:
            name = None
        if name is None:
            raise FormError, messages.MSG_BAD_NAME

        # Check the name is free
        if container.get_resource(name, soft=True) is not None:
            raise FormError, messages.MSG_NAME_CLASH
        form['name'] = name

        # Ok
        return form


    def set_value(self, resource, context, name, form):
        """Return True if an error occurs otherwise False. If an error
        occurs, the context.message must be an ERROR instance.
        """
        if name.endswith(('_time', '_year', '_day', '_month')):
            return False

        value = form[name]
        if type(value) is dict:
            for language, data in value.iteritems():
                resource.set_property(name, data, language=language)
        else:
            resource.set_property(name, value)
        return False


    def action(self, resource, context, form):
        # 1. Make the resource
        container = form['container']
        class_id = context.query['type']
        cls = get_resource_class(class_id)
        child = container.make_resource(form['name'], cls)
        # 2. Set properties
        schema = self.get_schema(resource, context)
        for name in self.fields:
            datatype = schema.get(name)
            if datatype and not getattr(datatype, 'readonly', False):
                if self.set_value(child, context, name, form):
                    return

        # Ok
        goto = str(resource.get_pathto(child))
        if self.goto_view:
            goto = '%s/;%s' % (goto, self.goto_view)
        return context.come_back(messages.MSG_NEW_RESOURCE, goto=goto)
