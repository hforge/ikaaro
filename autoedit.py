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

# Import from itools
from itools.datatypes import DateTime

# Import from ikaaro
from autoform import get_default_widget, timestamp_widget
from resource_views import DBResource_Edit


class AutoEdit(DBResource_Edit):

    fields = []


    def _get_schema(self, resource, context):
        schema = {'timestamp': DateTime(readonly=True)}

        # Add schema from the resource
        for name in self.fields:
            schema[name] = resource.class_schema[name]

        return schema


    def _get_widgets(self, resource, context):
        schema = resource.class_schema

        widgets = [timestamp_widget]
        for name in self.fields:
            datatype = schema[name]
            title = getattr(datatype, 'title', name)
            widget = get_default_widget(datatype)
            widget = widget(name, title=title)
            widgets.append(widget)

        return widgets
