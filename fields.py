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
from itools.core import thingy
from itools.database import magic
from itools.datatypes import String
from itools.handlers import get_handler_class_by_mimetype
from itools.html import XHTMLFile

# Import from ikaaro
from autoform import HTMLBody
from autoform import FileWidget, MultilineWidget, rte_widget



class Field(thingy):
    multilingual = False

    def get_value(self, resource, name, language=None):
        raise NotImplementedError

    def set_value(self, resource, name, value, language=None):
        """This method must return a boolean:

        - True if the value has changed
        - False if the value has NOT changed
        """
        raise NotImplementedError



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
            root = resource.get_site_root()
            languages = []
            for lang in root.get_property('website_languages'):
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


    def set_value(self, resource, name, value, language=None):
        """
        value may be:

        - None
        - a handler
        - a byte string
        - a tuple
        - something else
        """
        if self.multilingual and not language:
            raise ValueError, 'expected "language" param not found'

        # Case 1: None (XXX should remove instead?)
        if value is None:
            return False

        # Case 2: Set handler
        handler = self._get_handler_from_value(value)
        key = self._get_key(resource, name, language)
        database = resource.metadata.database
        if database.get_handler(key, soft=True):
            database.del_handler(key)
        database.set_handler(key, handler)
        return True # XXX It may be False


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
