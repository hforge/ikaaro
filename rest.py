# -*- coding: UTF-8 -*-
# Copyright (C) 2011 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2011 Hervé Cauwelier <herve@itaapy.com>
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
import json

# Import from itools
from itools.database import AndQuery, PhraseQuery
from itools.datatypes import String
from itools.handlers import checkid
from itools.web import BaseView

# Import from ikaaro
from fields import Metadata_Field
from utils import get_base_path_query


def property_to_json(field, prop):
    value = field.get_datatype().encode(prop.value)
    if not field.parameters_schema:
        return value

    value = {'value': value}
    if not prop.parameters:
        return value

    for name, datatype in field.parameters_schema.items():
        param_value = prop.parameters.get(name)
        if param_value is not None:
            value[name] = datatype.encode(param_value)

    return value


def field_to_json(resource, field_name):
    field = resource.get_field(field_name)
    if field is None:
        return None

    if issubclass(field, Metadata_Field):
        prop = resource.metadata.properties.get(field_name)
        if prop is None:
            return None
        if type(prop) is dict:
            prop = prop.values()
        if type(prop) is list:
            return [ property_to_json(field, x) for x in prop ]
        return property_to_json(field, prop)

    # TODO Files



class Rest_View(BaseView):
    """Generic REST exposure of a resource. Basis for a CRUD API.
    Export to JSON by default, extensible to other formats.
    """
    access = 'is_allowed_to_view'
    access_POST = 'is_allowed_to_add'
    access_PUT = 'is_allowed_to_edit'
    access_DELETE = 'is_allowed_to_remove'

    name_header = 'X-Create-Name'
    type_header = 'X-Create-Type'
    format_header = 'X-Create-Format'


    def POST(self, resource, context):
        """The C of CRUD: CREATE
        """
        # Read "bootstrap" from headers since body is used from metadata
        name = context.get_header(self.name_header)
        name = checkid(name)
        class_id = context.get_header(self.type_header)
        cls = context.database.get_resource_class(class_id)
        format = context.get_header(self.format_header)
        child = resource.make_resource(name, cls, format=format)
        # The rest is an update
        child.rest.PUT(child, context)
        # 201 Created
        context.status = 201
        # Return the URL of the new resource
        # XXX 201 may require empty body
        context.set_content_type('text/plain')
        return str(context.get_link(child))


    def GET(self, resource, context):
        """The R of CRUD: READ
        """
        # Build a dictionary represeting the resource by its schema.
        representation = {}
        for field_name in resource.fields:
            value = field_to_json(resource, field_name)
            if value is not None:
                representation[field_name] = value

        # Ok
        context.set_content_type('application/json')
        return json.dumps(representation)


    def PUT(self, resource, context):
        """The U of CRUD: UPDATE
        """
        data = context.get_form_value('data')
        representation = json.loads(data)
        for key, data in representation.iteritems():
            try:
                datatype = resource.get_property_datatype(key)
            except ValueError:
                pass
            # TODO encoding? though it should be UTF-8
            value = datatype.decode(data)
            # TODO language of multilingual properties from the headers?
            resource.set_property(key, value)
        # Empty 200 OK
        context.set_content_type('text/plain')
        return ''


    def DELETE(self, resource, context):
        """The D of CRUD: DELETE
        """
        # Delete myself
        resource.parent.del_resource(resource.name)
        # None means 204
        return None



class Rest_Query(BaseView):

    access = 'is_allowed_to_view'

    def GET(self, resource, context):
        field_names = context.get_query_value('fields', String(multiple=True))

        # Build the query
        query = get_base_path_query(resource.abspath)
        for key, value in context.uri.query.items():
            if key != 'fields':
                query = AndQuery(query, PhraseQuery(key, value))

        # Search
        items = []
        for resource in context.search(query).get_resources():
            item = {'abspath': str(resource.abspath)}
            for field_name in field_names:
                value = field_to_json(resource, field_name)
                if value is not None:
                    item[field_name] = value

            items.append(item)

        # Ok
        context.set_content_type('application/json')
        return json.dumps(items)
