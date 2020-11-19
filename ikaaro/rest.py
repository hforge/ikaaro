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
from base64 import b64encode, b64decode

# Import from itools
from itools.core import proto_lazy_property
from itools.web import BaseView

# Import from ikaaro
from fields import Metadata_Field, File_Field

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



def update_resource(resource, changes):
    for name, value, parameters in changes:
        # The value
        field = resource.get_field(name)
        if field is None:
            raise ValueError("undefined field '%s'" % name)
        if not field.access('write', resource):
            continue # XXX raise an error? log a message?
        if issubclass(field, File_Field):
            value = b64decode(value)
        else:
            datatype = field.get_datatype()
            value = datatype.decode(value)
        # The language
        lang = parameters.pop('lang', None)
        # Decode parameters
        for pname, pvalue in parameters.items():
            parameters[pname] = field.parameters_schema[pname].decode(pvalue)
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

    if not field.access('read', resource):
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

    # Computed
    value = field.get_value(resource, field_name)
    return {'value': value}


###########################################################################
# The CRUD Views
###########################################################################
class Rest_BaseView(BaseView):
    """Base class for other for the RESTful interface.
    """
    use_cookies = False


    @proto_lazy_property
    def json(self):
        """Utility method that loads the json from the request entity. Used
        by POST and PUT request methods.
        """
        return self.context.body


    def created(self, resource):
        context = self.context

        path = resource.abspath
        context.status = 201
        context.set_header('Location', str(context.uri.resolve(path)))
        context.set_content_type('text/plain')
        return str(path)
