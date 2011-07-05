# -*- coding: UTF-8 -*-
# Copyright (C) 2010 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2010-2011 Henry Obein <henry@itaapy.com>
# Copyright (C) 2010-2011 Taverne Sylvain <sylvain@itaapy.com>
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

# Import from the Standard Library
from datetime import datetime, date

# Import from itools
from itools.datatypes import DateTime, Date, Time
from itools.web import get_context

# Import from ikaaro
from autoform import get_default_widget, timestamp_widget
from resource_views import DBResource_Edit


class AutoEdit(DBResource_Edit):

    fields = []


    def get_query_schema(self):
        context = get_context()
        resource = context.resource

        schema = self._get_schema(resource, context)
        for name, datatype in schema.items():
            if getattr(datatype, 'mandatory', False) is True:
                schema[name] = datatype(mandatory=False)

        return schema


    def _get_datatype(self, resource, context, name):
        return resource.class_schema[name]


    def _get_schema(self, resource, context):
        schema = {'timestamp': DateTime(readonly=True)}

        # Add schema from the resource
        for name in self.fields:
            datatype = self._get_datatype(resource, context, name)

            # Special case: datetime
            if issubclass(datatype, DateTime):
                schema[name] = Date
                schema['%s_time' % name] = Time
                continue

            # Standard case
            schema[name] = datatype

        return schema


    def _get_widget(self, resource, context, name):
        datatype = resource.class_schema[name]
        title = getattr(datatype, 'title', name)
        widget = getattr(datatype, 'widget', None)
        if widget is None:
            widget = get_default_widget(datatype)
        return widget(name, title=title)


    def _get_widgets(self, resource, context):
        widgets = [timestamp_widget]
        for name in self.fields:
            widget = self._get_widget(resource, context, name)
            widgets.append(widget)

        return widgets


    def _get_form(self, resource, context):
        form = super(AutoEdit, self)._get_form(resource, context)
        # Combine date & time
        for name, value in form.items():
            if type(value) is date:
                value_time = form.get('%s_time' % name)
                if value_time is not None:
                    value = datetime.combine(value, value_time)
                    form[name] = context.fix_tzinfo(value)

        return form


    def get_value(self, resource, context, name, datatype):
        proxy = super(AutoEdit, self)
        if name[-5:] == '_time' and issubclass(datatype, Time):
            value = proxy.get_value(resource, context, name[:-5], DateTime)
            if type(value) is not datetime:
                return None
            value = value.time()
            context.query[name] = value
            return value

        return proxy.get_value(resource, context, name, datatype)


    def set_value(self, resource, context, name, form):
        if name[-5:] == '_time':
            return False

        proxy = super(AutoEdit, self)
        return proxy.set_value(resource, context, name, form)
