# -*- coding: UTF-8 -*-
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from itools.fs import FileName

# Import from ikaaro
from resource_ import DBResource


class Multilingual(DBResource):

    def __init__(self, metadata):
        self.metadata = metadata
        self.handlers = {}
        # The tree
        self.name = ''
        self.parent = None


    def init_resource(self, body=None, filename=None, language=None, **kw):
        DBResource.init_resource(self, filename=filename, **kw)
        if body:
            handler = self.class_handler(string=body)
            extension = handler.class_extension
            name = FileName.encode((self.name, extension, language))
            self.parent.handler.set_handler(name, handler)


    def get_handler(self, language=None):
        # Content language
        if language is None:
            site_root = self.get_site_root()
            ws_languages = site_root.get_property('website_languages')
            handlers = [
                (x, self.get_handler(language=x)) for x in ws_languages ]
            languages = [ x for (x, y) in handlers if not y.is_empty() ]
            language = select_language(languages)
            # Default
            if language is None:
                language = ws_languages[0]
        # Hit
        if language in self.handlers:
            return self.handlers[language]
        # Miss
        cls = self.class_handler
        metadata = self.metadata
        database = metadata.database
        name = FileName.encode((self.name, cls.class_extension, language))
        key = database.fs.resolve(metadata.key, name)
        handler = database.get_handler(key, cls=cls, soft=True)
        if handler is None:
            handler = cls()
            database.push_phantom(key, handler)

        self.handlers[language] = handler
        return handler

    handler = property(get_handler, None, None, '')


    def get_handlers(self):
        languages = self.get_site_root().get_property('website_languages')
        return [ self.get_handler(language=x) for x in languages ]


    def rename_handlers(self, new_name):
        old_name = self.name
        extension = self.class_handler.class_extension
        langs = self.get_site_root().get_property('website_languages')

        return [ (FileName.encode((old_name, extension, x)),
                  FileName.encode((new_name, extension, x)))
                 for x in langs ]


    def to_text(self, languages=None):
        if languages is None:
            languages = self.get_site_root().get_property('website_languages')
        result = {}
        for language in languages:
            handler = self.get_handler(language=language)
            result[language] = handler.to_text()
        return result
