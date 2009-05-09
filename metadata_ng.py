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
from itools.csv import parse_table, Property
from itools.datatypes import String
from itools.handlers import File

# Import from ikaaro
from registry import get_resource_class


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
            # Get the datatype
            datatype = schema[name]
            multiple = is_multiple(datatype)
            multilingual = is_multilingual(datatype)
            if multiple and multilingual:
                error = 'property "%s" is both multilingual and multiple'
                raise ValueError, error % name
            # Build the property
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


    ########################################################################
    # API
    ########################################################################
    def get_property_and_language(self, name, language=None):
        """Return the value for the given property and the language of that
        value.

        For monolingual properties, the language always will be None.
        """
        # Check the property exists
        datatype = get_datatype(self.format, name)
        if name not in self.properties:
            default = datatype.get_default()
            return default, None
        # Get the value
        value = self.properties[name]

        # Monolingual property
        if not isinstance(value, dict):
            return value, None

        # Language negotiation
        if language is None:
            context = get_context()
            if context is None:
                language = None
            else:
                languages = [
                    k for k, v in value.items() if not datatype.is_empty(v) ]
                accept = context.accept_language
                language = accept.select_language(languages)
            # Default (FIXME pick one at random)
            if language is None:
                language = value.keys()[0]
            return value[language], language

        if language in value:
            return value[language], language
        return datatype.get_default(), None


    def get_property(self, name, language=None):
        return self.get_property_and_language(name, language=language)[0]

