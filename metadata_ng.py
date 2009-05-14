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
from itools.csv import parse_table, Property, property_to_str
from itools.datatypes import String
from itools.handlers import File

# Import from ikaaro
from registry import get_resource_class


# This is the datatype used for properties not defined in the schema
multiple_datatype = String(multiple=True, multilingual=False)
multilingual_datatype = String(multiple=False, multilingual=True)



def get_schema(format):
    cls = get_resource_class(format)
    return cls.get_metadata_schema()


def get_datatype(format, name):
    schema = get_schema(format)
    if name not in schema:
        return String
    return schema[name]


def is_multiple(datatype):
    return getattr(datatype, 'multiple', False)


def is_multilingual(datatype):
    return getattr(datatype, 'multilingual', False)



class MetadataNG(File):

    def reset(self):
        self.format = None
        self.properties = {}


    def new(self, cls=None, format=None):
        self.format = format or cls.class_id
        self.properties['version'] = Property(cls.class_version)


    def _load_state_from_file(self, file):
        properties = self.properties
        data = file.read()
        parser = parse_table(data)

        # Read the format
        name, value, parameters = parser.next()
        if name != 'format':
            raise ValueError, 'unexpected "%s" property' % name
        if parameters:
            raise ValueError, 'unexpected parameters for the format property'
        self.format = value
        # Get the schema
        schema = get_schema(value)

        # Parse
        for name, value, parameters in parser:
            if name == 'format':
                raise ValueError, 'unexpected "format" property'

            # 1. Get the datatype
            datatype = schema.get(name)
            if not datatype:
                # Guess the datatype for properties not defined by the schema
                if 'lang' in parameters:
                    datatype = multilingual_datatype
                else:
                    datatype = multiple_datatype

            # 2. Get the datatype properties
            multiple = is_multiple(datatype)
            multilingual = is_multilingual(datatype)
            if multiple and multilingual:
                error = 'property "%s" is both multilingual and multiple'
                raise ValueError, error % name

            # 3. Build the property
            value = datatype.decode(value)
            property = Property(value, **parameters)

            # Case 1: Multilingual
            if multilingual:
                language = parameters.get('lang')
                if language is None:
                    err = 'multilingual property "%s" is missing the language'
                    raise ValueError, err % name
                language = language[0]
                properties.setdefault(name, {})[language] = property
            # Case 2: multiple
            elif multiple:
                raise NotImplementedError
            # Case 3: simple
            else:
                properties[name] = property


    def to_str(self):
        schema = get_schema(self.format)
        p_schema = {'lang': String(multiple=False)}

        lines = []
        lines.append('format:%s\n' % self.format)
        # Define the order by which the properties should be serialized
        # (first the version, then by alphabetical order)
        properties = self.properties
        names = properties.keys()
        names.sort()
        if 'version' in names:
            names.remove('version')
            names.insert(0, 'version')

        # Properties
        for name in names:
            property = properties[name]
            datatype = schema[name]
            p_type = type(property)
            if p_type is dict:
                languages = property.keys()
                languages.sort()
                lines += [
                    property_to_str(name, property[x], datatype, p_schema)
                    for x in languages ]
            elif p_type is list:
                lines += [
                    property_to_str(name, x, datatype, p_schema)
                    for x in property ]
            else:
                lines.append(
                    property_to_str(name, property, datatype, p_schema))

        return ''.join(lines)


    ########################################################################
    # API
    ########################################################################
    def _get_property(self, name, language=None):
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
        datatype = get_datatype(self.format, name)
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


    def get_property(self, name, language=None):
        """Return the property value for the given property name.
        """
        property = self._get_property(name, language=language)
        # Default
        if not property:
            datatype = get_datatype(self.format, name)
            return datatype.get_default()

        # Multiple
        if type(property) is list:
            return [ x.value for x in property ]

        # Simple
        return property.value


    def set_property(self, name, value):
        self.set_changed()
        properties = self.properties

        if value is None:
            # Remove property
            if name in properties:
                del properties[name]
        elif type(value) is Property:
            language = value.parameters.get('lang')
            if language:
                properties.setdefault(name, {})[language] = value
            else:
                properties[name] = value
        else:
            properties[name] = Property(value)

