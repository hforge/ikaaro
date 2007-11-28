# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from itools.datatypes import FileName


class Multilingual(object):

    def __init__(self, metadata):
        self.metadata = metadata
        self.handlers = {}
        # The tree
        self.name = ''
        self.parent = None


    def get_handler(self, language=None):
        # Content language
        if language is None:
            language = self.get_content_language()
        # Hit
        if language in self.handlers:
            return self.handlers[language]
        # Miss
        cls = self.class_handler
        database = self.metadata.database
        name = FileName.encode((self.name, cls.class_extension, language))
        uri = self.metadata.uri.resolve(name)
        if database.has_handler(uri):
            handler = database.get_handler(uri, cls=cls)
        else:
            handler = cls()
            handler.database = database
            handler.uri = uri
            handler.timestamp = None
            handler.dirty = True
            database.cache[uri] = handler

        self.handlers[language] = handler
        return handler

    handler = property(get_handler, None, None, '')


    def get_handlers(self):
        site_root = self.get_site_root()
        languages = site_root.get_property('ikaaro:website_languages')
        return [ self.get_handler(language=x) for x in languages ]


    def rename_handlers(self, new_name):
        old_name = self.name
        extension = self.class_handler.class_extension
        langs = self.get_site_root().get_property('ikaaro:website_languages')

        return [ (FileName.encode((old_name, extension, x)),
                  FileName.encode((new_name, extension, x)))
                 for x in langs ]

