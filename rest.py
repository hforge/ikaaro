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
from base64 import b64encode
import json

# Import from itools
from itools.database import AndQuery, PhraseQuery
from itools.datatypes import String
from itools.handlers import checkid
from itools.web import BaseView

# Import from ikaaro
from fields import Metadata_Field, File_Field
from resource_views import LoginView
from utils import get_base_path_query


###########################################################################
# Utility functions
###########################################################################
def fix_json(obj):
    """Utility function, given a json object as returned by json.loads
    transform the unicode strings to strings.

    TODO Use a custom JSONDecoder instead.
    """
    obj_type = type(obj)
    if obj_type is unicode:
        return obj.encode('utf-8')
    if obj_type is list:
        return [ fix_json(x) for x in obj ]
    if obj_type is dict:
        aux = {}
        for x, y in obj.items():
            aux[fix_json(x)] = fix_json(y)
        return aux
    return obj


def load_json(context):
    """Utility method that loads the json from the request entity. Used
    by POST and PUT request methods.
    """
    data = context.body['body']
    data = json.loads(data) # TODO Use a custom JSONDecoder
    return fix_json(data)



def update_resource(resource, changes):
    for name, value, parameters in changes:
        # The value
        datatype = resource.get_field(name).get_datatype()
        value = datatype.decode(value)
        # The language
        lang = parameters.pop('lang', None)
        # Action
        resource.set_value(name, value, lang, **parameters)


def property_to_json(field, prop):
    # The value
    value = field.get_datatype().encode(prop.value)
    value = {'value': value}

    # The parameters
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

    # Metadata
    if issubclass(field, Metadata_Field):
        prop = resource.metadata.properties.get(field_name)
        if prop is None:
            return None
        if type(prop) is dict:
            prop = prop.values()
        if type(prop) is list:
            return [ property_to_json(field, x) for x in prop ]
        return property_to_json(field, prop)

    # Files
    if issubclass(field, File_Field):
        handler = field.get_value(resource, field_name)
        if not handler:
            return None
        return {'value': b64encode(handler.to_str())}

    # Error
    raise ValueError, 'unexpected field type %s' % repr(field)



###########################################################################
# Login
###########################################################################
class Rest_Login(LoginView):

    def POST(self, resource, context):
        super(Rest_Login, self).POST(resource, context)
        # Failed
        user = context.user
        if user is None:
            return None
        # Ok
        context.set_content_type('text/plain')
        return str(user.abspath)



###########################################################################
# The CRUD Views
###########################################################################
class Rest_Read(BaseView):
    """The R of CRUD: READ
    """

    access = 'is_allowed_to_view'

    def GET(self, resource, context):
        # Build a dictionary represeting the resource by its schema.
        representation = {}
        representation['format'] = {'value': resource.class_id}
        for field_name in resource.fields:
            value = field_to_json(resource, field_name)
            if value is not None:
                representation[field_name] = value

        # Set last modification time
        mtime = resource.get_value('mtime')
        context.set_header('Last-Modified', mtime)

        # Ok
        context.set_content_type('application/json')
        return json.dumps(representation)


class Rest_Create(BaseView):
    """The C of CRUD: CREATE
    """

    access = 'is_allowed_to_add'

    def POST(self, resource, context):
        name, class_id, changes = load_json(context)

        # 1. Make the resource
        if name is not None:
            name = checkid(name)
        cls = context.database.get_resource_class(class_id)
        child = resource.make_resource(name, cls)
        # 2. Modify the resource
        update_resource(child, changes)

        # 3. Return the URL of the new resource
        path = child.abspath
        context.status = 201
        context.set_header('Location', str(context.uri.resolve(path)))
        context.set_content_type('text/plain')
        return str(path)



class Rest_Update(BaseView):
    """The U of CRUD: UPDATE
    """

    access = 'is_allowed_to_edit'

    def POST(self, resource, context):
        changes = load_json(context)
        update_resource(resource, changes)

        # Empty 200 OK
        context.set_content_type('text/plain')
        return ''


#   access_DELETE = 'is_allowed_to_remove'
#   def DELETE(self, resource, context):
#       """The D of CRUD: DELETE
#       """
#       # Delete myself
#       resource.parent.del_resource(resource.name)
#       # None means 204
#       return None



###########################################################################
# Other views
###########################################################################
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



class Rest_Schema(BaseView):

    access = 'is_allowed_to_view'


    def GET(self, resource, context):
        schema = {}
        for name, field in resource.get_fields():
            schema[name] = field.rest()

        # Ok
        context.set_content_type('application/json')
        return json.dumps(schema)
