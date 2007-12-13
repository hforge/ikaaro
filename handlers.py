# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from datetime import datetime
import mimetypes
from random import random
from time import time

# Import from itools
from itools.datatypes import is_datatype, DateTime, String, Unicode, XML
from itools.handlers import File, TextFile, register_handler_class
from itools.schemas import get_schema_by_uri, get_schema
from itools.web import get_context
from itools.xml import (XMLNamespace, XMLParser, START_ELEMENT, END_ELEMENT,
    TEXT)

# Import from ikaaro
from metadata import Record
from registry import get_object_class



###########################################################################
# Lock
###########################################################################
class Lock(TextFile):

    class_mimetypes = ['text/x-lock']
    class_extension = 'lock'


    def new(self, username=None, **kw):
        self.username = username
        self.lock_timestamp = datetime.now()
        self.key = '%s-%s-00105A989226:%.03f' % (random(), random(), time())


    def _load_state_from_file(self, file):
        username, timestamp, key = file.read().strip().split('\n')
        self.username = username
        # XXX backwards compatibility: remove microseconds first
        timestamp = timestamp.split('.')[0]
        self.lock_timestamp = DateTime.decode(timestamp)
        self.key = key


    def to_str(self):
        timestamp = DateTime.encode(self.lock_timestamp)
        return '%s\n%s\n%s' % (self.username, timestamp, self.key)


###########################################################################
# Metadata
###########################################################################

class ParserError(Exception):
    pass


def get_datatype(format, name):
    if format is None:
        return String

    cls = get_object_class(format)
    if cls is None:
        return String

    schema = cls.get_metadata_schema()
    return schema.get(name, String)



class Metadata(File):

    class_mimetypes = ['text/x-metadata']
    class_extension = 'metadata'


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
        xml_lang = (XMLNamespace.class_uri, 'lang')
        error1 = 'unexpected start tag "%s" at line "%s"'
        # Local variables
        language = None
        stack = []

        # Parse
        for type, value, line in XMLParser(file.read()):
            if type == START_ELEMENT:
                ns_uri, name, attributes = value
                if ns_uri is not None:
                    prefix = get_schema_by_uri(ns_uri).class_prefix
                    name = '%s:%s' % (prefix, name)

                # First tag: <metadata>
                n = len(stack)
                if n == 0:
                    if name != 'metadata':
                        raise ParserError, error1 % (name, line)
                    self.format = attributes.get((None, 'format'))
                    self.version = attributes.get((None, 'version'))
                    if self.format is None:
                        schema = {}
                    else:
                        cls = get_object_class(self.format)
                        schema = cls.get_metadata_schema()
                    stack.append((name, None, {}))
                    continue

                # Find out datatype
                if n == 1:
                    datatype = schema.get(name, String)
                else:
                    datatype = stack[-1][1]
                    if is_datatype(datatype, Record):
                        datatype = datatype.schema.get(name, String)
                    else:
                        raise ParserError, error1 % (name, line)

                if is_datatype(datatype, Record):
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
                if is_datatype(datatype, Record):
                    pass
                elif is_datatype(datatype, Unicode):
                    value = datatype.decode(value, 'utf-8')
                else:
                    value = datatype.decode(value)

                # Set property
                if isinstance(datatype.default, list):
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
        cls = get_object_class(format)
        if cls is None:
            schema = {}
        else:
            schema = cls.get_metadata_schema()

        # Opening
        lines = ['<metadata format="%s" version="%s">\n' % (format, version)]

        # Properties
        for name in self.properties:
            value = self.properties[name]
            datatype = schema.get(name, String)

            # Multilingual properties
            if isinstance(value, dict):
                template = '  <%s xml:lang="%s">%s</%s>\n'
                for language, value in value.items():
                    value = datatype.encode(value)
                    value = XML.encode(value)
                    lines.append(template % (name, language, value, name))
            # Multiple values
            elif isinstance(value, list):
                # Record
                if is_datatype(datatype, Record):
                    aux = datatype.schema
                    for value in value:
                        lines.append('  <%s>\n' % name)
                        for key, value in value.items():
                            value = aux.get(key).encode(value)
                            value = XML.encode(value)
                            lines.append('    <%s>%s</%s>\n'
                                         % (key, value, key))
                        lines.append('  </%s>\n' % name)
                    continue
                # Regular field
                for value in value:
                    value = datatype.encode(value)
                    value = XML.encode(value)
                    lines.append('  <%s>%s</%s>\n' % (name, value, name))
                continue
            # Simple properties
            else:
                value = datatype.encode(value)
                value = XML.encode(value)
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
            return datatype.default, None
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
                languages = [ k for k, v in value.items() if v.strip() ]
                accept = context.accept_language
                language = accept.select_language(languages)
            # Default (FIXME pick one at random)
            if language is None:
                language = value.keys()[0]
            return value[language], language

        if language in value:
            return value[language], language
        return datatype.default, None


    def get_property(self, name, language=None):
        return self.get_property_and_language(name, language=language)[0]


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

            default = datatype.default
            if isinstance(default, list):
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



###########################################################################
# Register
###########################################################################
for handler_class in [Lock, Metadata]:
    register_handler_class(handler_class)
    for mimetype in handler_class.class_mimetypes:
        mimetypes.add_type(mimetype, '.%s' % handler_class.class_extension)

