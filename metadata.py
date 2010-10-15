# -*- coding: UTF-8 -*-
# Copyright (C) 2009 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from itools.core import add_type
from itools.csv import parse_table, Property, property_to_str
from itools.csv import deserialize_parameters
from itools.datatypes import String
from itools.handlers import File, register_handler_class
from itools.web import get_context

# Import from ikaaro
from registry import get_resource_class


# This is the datatype used for properties not defined in the schema
multiple_datatype = String(multiple=True, multilingual=False)
multilingual_datatype = String(multiple=False, multilingual=True,
                               parameters_schema={'lang': String})


def is_multiple(datatype):
    return getattr(datatype, 'multiple', False)


def is_multilingual(datatype):
    return getattr(datatype, 'multilingual', False)


def get_parameters_schema(datatype):
    return getattr(datatype, 'parameters_schema', {})



class Metadata(File):

    class_mimetypes = ['text/x-metadata']
    class_extension = 'metadata'


    def reset(self):
        self.format = None
        self.version = None
        self.properties = {}


    def new(self, cls=None, format=None, version=None):
        self.format = format or cls.class_id
        self.version = version or cls.class_version


    def _load_state_from_file(self, file):
        properties = self.properties
        data = file.read()
        parser = parse_table(data)

        # Read the format & version
        name, value, parameters = parser.next()
        if name != 'format':
            raise ValueError, 'unexpected "%s" property' % name
        if 'version' in parameters:
            version = parameters.pop('version')
            if len(version) > 1:
                raise ValueError, 'version parameter cannot be repeated'
            self.version = version[0]
        if parameters:
            raise ValueError, 'unexpected parameters for the format property'
        self.format = value
        # Get the schema
        resource_class = get_resource_class(value)

        # Parse
        for name, value, parameters in parser:
            if name == 'format':
                raise ValueError, 'unexpected "format" property'

            # 1. Get the datatype
            datatype = resource_class.get_property_datatype(name)
            if not datatype:
                # Guess the datatype for properties not defined by the schema
                if 'lang' in parameters:
                    datatype = multilingual_datatype
                else:
                    datatype = multiple_datatype

            # 2. Deserialize the parameters
            parameters_schema = get_parameters_schema(datatype)
            deserialize_parameters(parameters, parameters_schema)

            # 3. Get the datatype properties
            multiple = is_multiple(datatype)
            multilingual = is_multilingual(datatype)
            if multiple and multilingual:
                error = 'property "%s" is both multilingual and multiple'
                raise ValueError, error % name

            # 4. Build the property
            value = datatype.decode(value)
            property = Property(value, **parameters)

            # Case 1: Multilingual
            if multilingual:
                language = parameters.get('lang')
                if language is None:
                    err = 'multilingual property "%s" is missing the language'
                    raise ValueError, err % name
                properties.setdefault(name, {})[language] = property
            # Case 2: multiple
            elif multiple:
                properties.setdefault(name, []).append(property)
            # Case 3: simple
            else:
                properties[name] = property


    def to_str(self):
        resource_class = get_resource_class(self.format)

        if self.version is None:
            lines = ['format:%s\n' % self.format]
        else:
            lines = ['format;version=%s:%s\n' % (self.version, self.format)]
        # Properties are to be sorted by alphabetical order
        properties = self.properties
        names = properties.keys()
        names.sort()

        # Properties
        for name in names:
            property = properties[name]
            datatype = resource_class.get_property_datatype(name, String)
            params_schema = get_parameters_schema(datatype)
            is_empty = datatype.is_empty
            p_type = type(property)
            if p_type is dict:
                languages = property.keys()
                languages.sort()
                lines += [
                    property_to_str(name, property[x], datatype, params_schema)
                    for x in languages if not is_empty(property[x].value) ]
            elif p_type is list:
                lines += [
                    property_to_str(name, x, datatype, params_schema)
                    for x in property if not is_empty(x.value) ]
            elif property.value is None:
                pass
            elif not is_empty(property.value):
                lines.append(
                    property_to_str(name, property, datatype, params_schema))

        return ''.join(lines)


    ########################################################################
    # API
    ########################################################################
    def get_property(self, name, language=None):
        """Return the property for the given property name.  If it is missing
        return None.

        If it is a multilingual property, return only the property for the
        given language (negotiate the language if needed).

        If it is a multiple property, return the list of properties.
        """
        # Return 'None' if the property is missing
        property = self.properties.get(name)
        if not property:
            return None

        # Monolingual property, we are done
        if type(property) is not dict:
            return property

        # The language has been given
        if language:
            return property.get(language)

        # Consider only the properties with a non empty value
        cls = get_resource_class(self.format)
        datatype = cls.get_property_datatype(name)
        languages = [
            x for x in property if not datatype.is_empty(property[x].value) ]
        if not languages:
            return None

        # Negotiate the language (if the context is available)
        context = get_context()
        if context:
            language = context.accept_language.select_language(languages)
        else:
            language = None

        # Negotiation failed, pick a language at random
        # FIXME We can do better than this
        if language is None:
            language = languages[0]

        return property[language]


    def has_property(self, name, language=None):
        if name not in self.properties:
            return False

        if language is not None:
            return language in self.properties[name]

        return True


    def _set_property(self, name, value):
        properties = self.properties

        # Case 1: Remove property
        if value is None:
            if name in properties:
                del properties[name]
            return

        # Case 2: Multiple (replace)
        p_type = type(value)
        if p_type is list:
            properties[name] = [
                x if type(x) is Property else Property(x) for x in value ]
            return

        # Case 3: Multilingual
        if p_type is Property:
            if value.parameters and 'lang' in value.parameters:
                language = value.parameters['lang']
                properties.setdefault(name, {})[language] = value
                return
        else:
            value = Property(value)

        # Case 4: Simple
        cls = get_resource_class(self.format)
        datatype = cls.get_property_datatype(name)
        if datatype is None or getattr(datatype, 'multiple', False) is False:
            properties[name] = value
            return

        # Case 5: Multiple (append)
        cls = get_resource_class(self.format)
        datatype = cls.get_property_datatype(name)
        if not datatype.is_empty(value.value):
            properties.setdefault(name, []).append(value)


    def set_property(self, name, value):
        self.set_changed()
        self._set_property(name, value)


    def del_property(self, name):
        if name in self.properties:
            self.set_changed()
            del self.properties[name]


###########################################################################
# Register
###########################################################################
register_handler_class(Metadata)
for mimetype in Metadata.class_mimetypes:
    add_type(mimetype, '.%s' % Metadata.class_extension)

