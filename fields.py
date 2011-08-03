# -*- coding: UTF-8 -*-
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

# Impor from itools
from itools.core import freeze, thingy
from itools.csv import Property
from itools.database import magic
from itools.datatypes import Boolean, Date, DateTime, Email, Enumerate
from itools.datatypes import Integer, String, Unicode, URI
from itools.handlers import get_handler_class_by_mimetype
from itools.html import XHTMLFile
from itools.web import get_context

# Import from ikaaro
from autoform import HTMLBody, Widget
from autoform import BirthDateWidget, DateWidget, DatetimeWidget, FileWidget
from autoform import MultilineWidget, RadioWidget, SelectWidget, TextWidget
from autoform import rte_widget
from datatypes import BirthDate, Password



class Field(thingy):

    datatype = None
    default = None
    multilingual = False
    multiple = False
    indexed = False
    stored = False
    required = False
    title = None
    hidden_by_default = False
    readonly = False # Means the field should not be editable by the user

    def get_value(self, resource, name, language=None):
        raise NotImplementedError


    def set_value(self, resource, name, value, language=None):
        """If value == old value then return False
           else make the change and return True
        """
        # Check the new value is different from the old value
        old_value = self.get_value(resource, name, language)
        if value == old_value:
            return False

        # Set property
        self._set_value(resource, name, value, language)
        get_context().database.change_resource(resource)
        return True


    # XXX For backwards compatibility
    datatype_keys = [
        'default', 'multiple', 'multilingual', 'indexed', 'stored', 'widget',
        'hidden_by_default']
    def get_datatype(self):
        kw = {}
        for key in self.datatype_keys:
            value = getattr(self, key)
            if value is not None:
                kw[key] = value

        return self.datatype(mandatory=self.required, title=self.title, **kw)


    def get_default(self):
        if self.default is not None:
            return self.default
        return self.get_datatype().get_default()



###########################################################################
# Metadata properties
###########################################################################
class Metadata_Field(Field):

    parameters_schema = freeze({})
    parameters_schema_default = None
    widget = Widget


    def get_value(self, resource, name, language=None):
        property = resource.metadata.get_property(name, language=language)
        if not property:
            return self.get_default()

        # Multiple
        if type(property) is list:
            return [ x.value for x in property ]

        # Simple
        return property.value


    def _set_value(self, resource, name, value, language=None):
        if language:
            value = Property(value, lang=language)
        resource.metadata.set_property(name, value)



class Birthdate_Field(Metadata_Field):
    datatype = BirthDate
    widget = BirthDateWidget



class Boolean_Field(Metadata_Field):
    datatype = Boolean
    widget = RadioWidget



class Char_Field(Metadata_Field):
    datatype = String
    widget = TextWidget



class Date_Field(Metadata_Field):
    datatype = Date
    widget = DateWidget



class Datetime_Field(Metadata_Field):
    datatype = DateTime
    widget = DatetimeWidget



class Email_Field(Metadata_Field):
    datatype = Email



class Integer_Field(Metadata_Field):
    datatype = Integer



class Password_Field(Metadata_Field):
    datatype = Password



class Select_Field(Metadata_Field):
    datatype = Enumerate
    widget = SelectWidget
    options = None # Must be overriden by subclasses: [{}, ...]

    datatype_keys = Metadata_Field.datatype_keys + ['options']



class Text_Field(Metadata_Field):
    datatype = Unicode
    multilingual = True
    parameters_schema = {'lang': String} # useful only when multilingual
    widget = TextWidget



class Textarea_Field(Text_Field):
    widget = MultilineWidget



class URI_Field(Metadata_Field):
    datatype = URI

###########################################################################
# File handlers
###########################################################################
class File_Field(Field):

    class_handler = None
    datatype = String
    widget = FileWidget


    def _get_key(self, resource, name, language):
        base = resource.metadata.key[:-9]
        if language:
            return '%s.%s.%s' % (base, name, language)

        return '%s.%s' % (base, name)


    def get_value(self, resource, name, language=None):
        cls = self.class_handler
        get_handler = resource.metadata.database.get_handler

        # Language negotiation
        if self.multilingual and language is None:
            root = resource.get_root()
            languages = []
            for lang in root.get_value('website_languages'):
                key = self._get_key(resource, name, lang)
                handler = get_handler(key, cls, soft=True)
                if handler:
                    languages.append(lang)

            language = select_language(languages)
            if language is None:
                if not languages:
                    return None
                language = languages[0]

        # Ok
        key = self._get_key(resource, name, language)
        return get_handler(key, cls=cls, soft=True)


    def _set_value(self, resource, name, value, language=None):
        """
        value may be:

        - None (XXX remove handler?)
        - a handler
        - a byte string
        - a tuple
        - something else
        """
        if self.multilingual and not language:
            raise ValueError, 'expected "language" param not found'

        # Set handler
        handler = self._get_handler_from_value(value)
        key = self._get_key(resource, name, language)
        database = resource.metadata.database
        if database.get_handler(key, soft=True):
            database.del_handler(key)
        database.set_handler(key, handler)


    def _get_handler_from_value(self, value):
        if type(value) is tuple:
            filename, mimetype, value = value

        if type(value) is str:
            cls = self.class_handler
            if cls is None:
                mimetype = magic.buffer(value)
                cls = get_handler_class_by_mimetype(mimetype)
            return cls(string=value)

        return value



class TextFile_Field(File_Field):

    widget = MultilineWidget



class HTMLFile_Field(File_Field):

    class_handler = XHTMLFile
    datatype = HTMLBody
    multilingual = True
    widget = rte_widget


    def _get_handler_from_value(self, value):
        if type(value) is list:
            handler = self.class_handler()
            handler.set_body(value)
            return handler

        return super(HTMLFile_Field, self)._get_handler_from_value(value)
