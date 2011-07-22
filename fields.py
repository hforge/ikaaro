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
from itools.datatypes import String
from itools.handlers import File

# Import from ikaaro
from autoform import FileWidget, MultilineWidget



class Field(thingy):
    pass


class File_Field(Field):

    class_handler = None
    datatype = String
    widget = FileWidget

    def get_value(self, resource, name, language=None):
        cls = self.class_handler
        database = resource.metadata.database
        key = '%s.%s' % (resource.metadata.key[:-9], name)
        return database.get_handler(key, cls=cls, soft=True)


    def set_value(self, resource, name, value, language=None):
        if value is None:
            return
        if type(value) is not str:
            filename, mimetype, value = value

        handler = self.get_value(resource, name, language)

        # Case 1: set a new handler
        if handler is None:
            database = resource.metadata.database
            key = '%s.%s' % (resource.metadata.key[:-9], name)
            if type(value) is str:
                value = File(string=value)
            database.set_handler(key, value)
            return

        # Case 2: modify an existing handler
        try:
            handler.load_state_from_string(value)
        except Exception:
            handler.load_state()
            raise



class TextFile_Field(File_Field):

    widget = MultilineWidget
