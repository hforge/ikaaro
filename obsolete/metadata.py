# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2009 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
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
from itools.core import freeze
from itools.csv import Property
from itools.datatypes import DataType, String, Unicode, XMLContent
from itools.handlers import File
from itools.web import get_context
from itools.xml import xml_uri, XMLParser, START_ELEMENT, END_ELEMENT, TEXT

# Import from ikaaro
from ikaaro.exceptions import ParserError
from ikaaro.registry import get_resource_class


###########################################################################
# XXX Backwards compatibility with 0.50
###########################################################################
class Record(DataType):

    # Set your own default list to avoid sharing this instance
    default = freeze([])
    schema = {}

    multiple = True



def get_datatype(format, name):
    if format is None:
        return String

    cls = get_resource_class(format)
    if cls is None:
        return String

    return cls.get_property_datatype(name)



class OldMetadata(File):

    def new(self, handler_class=None, format=None, **kw):
        # Add format and version
        self.format = format or handler_class.class_id
        self.version = handler_class.class_version

        # Initialize
        properties = {}
        for name in kw:
            value = kw[name]
            if value is not None:
                properties[name] = value

        # Set state
        self.properties = properties


    def _load_state_from_file(self, file):
        # Constants
        xml_lang = (xml_uri, 'lang')
        error1 = 'unexpected start tag "%s" at line "%s"'
        # Local variables
        language = None
        stack = []

        # Parse
        for type, value, line in XMLParser(file.read()):
            if type == START_ELEMENT:
                ns_uri, name, attributes = value
                # First tag: <metadata>
                n = len(stack)
                if n == 0:
                    if name != 'metadata':
                        raise ParserError, error1 % (name, line)
                    self.format = attributes.get((None, 'format'))
                    self.version = attributes.get((None, 'version'))
                    stack.append((name, None, {}))
                    continue

                # Find out datatype
                if n == 1:
                    datatype = get_datatype(self.format, name)
                else:
                    datatype = stack[-1][1]
                    if issubclass(datatype, Record):
                        datatype = datatype.schema.get(name, String)
                    else:
                        raise ParserError, error1 % (name, line)

                if issubclass(datatype, Record):
                    stack.append((name, datatype, {}))
                else:
                    stack.append((name, datatype, ''))
                    language = attributes.get(xml_lang)
            elif type == END_ELEMENT:
                name, datatype, value = stack.pop()

                # Last tag: </metadata>
                n = len(stack)
                if n == 0:
                    self.properties = value
                    break

                # Decode value
                if issubclass(datatype, Record):
                    pass
                elif issubclass(datatype, Unicode):
                    value = datatype.decode(value, 'utf-8')
                else:
                    value = datatype.decode(value)

                # Set property
                is_multiple = getattr(datatype, 'multiple', False)
                if is_multiple:
                    stack[-1][2].setdefault(name, []).append(value)
                elif language is None:
                    stack[-1][2][name] = value
                else:
                    stack[-1][2].setdefault(name, {})
                    stack[-1][2][name][language] = value
                # Reset variables
                language = None
            elif type == TEXT:
                n = len(stack)
                if n == 0:
                    continue
                if isinstance(stack[-1][2], dict):
                    continue

                name, datatype, last_value = stack.pop()
                value = last_value + value
                stack.append((name, datatype, value))


    def to_str(self):
        # format, version, schema
        format = self.format
        version = self.version

        # Opening
        lines = ['<?xml version="1.0" encoding="UTF-8"?>\n',
                 '<metadata format="%s" version="%s">\n' % (format, version)]

        # Sort properties
        names = self.properties.keys()
        names.sort()

        # Properties
        for name in names:
            value = self.properties[name]
            datatype = get_datatype(format, name)
            default = datatype.get_default()
            is_multiple = getattr(datatype, 'multiple', False)

            # Multilingual properties
            if isinstance(value, dict):
                template = '  <%s xml:lang="%s">%s</%s>\n'
                for language, value in value.items():
                    if value != default:
                        value = datatype.encode(value)
                        value = XMLContent.encode(value)
                        lines.append(template % (name, language, value, name))
            # Multiple values
            elif is_multiple:
                if not isinstance(value, list):
                    raise TypeError, 'multiple values must be lists'
                # Record
                if issubclass(datatype, Record):
                    aux = datatype.schema
                    for value in value:
                        lines.append('  <%s>\n' % name)
                        for key, value in value.items():
                            value = aux.get(key, String).encode(value)
                            value = XMLContent.encode(value)
                            lines.append('    <%s>%s</%s>\n'
                                         % (key, value, key))
                        lines.append('  </%s>\n' % name)
                    continue
                # Regular field
                for value in value:
                    value = datatype.encode(value)
                    value = XMLContent.encode(value)
                    lines.append('  <%s>%s</%s>\n' % (name, value, name))
                continue
            # Simple properties
            elif value != default:
                value = datatype.encode(value)
                if type(value) is not str:
                    message = 'in "%s", property "%s" not encoded'
                    raise TypeError, message % (self.key, name)
                value = XMLContent.encode(value)
                lines.append('  <%s>%s</%s>\n' % (name, value, name))

        lines.append('</metadata>\n')
        return ''.join(lines)


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
        if name not in self.properties:
            return None
        value, lang = self.get_property_and_language(name, language=language)
        if lang:
            return Property(value, lang=lang)
        return Property(value)


    def has_property(self, name, language=None):
        if name not in self.properties:
            return False

        if language is not None:
            return language in self.properties[name]

        return True


    def set_property(self, name, value, language=None):
        self.set_changed()

        # Set the value
        if language is None:
            datatype = get_datatype(self.format, name)
            is_multiple = getattr(datatype, 'multiple', False)

            if is_multiple:
                if isinstance(value, list):
                    self.properties[name] = value
                else:
                    values = self.properties.setdefault(name, [])
                    values.append(value)
            else:
                self.properties[name] = value
        else:
            values = self.properties.setdefault(name, {})
            values[language] = value


    def del_property(self, name, language=None):
        if name in self.properties:
            if language is None:
                self.set_changed()
                del self.properties[name]
            else:
                values = self.properties[name]
                if language in values:
                    self.set_changed()
                    del values[language]

