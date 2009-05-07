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
from itools.handlers import File

# Import from ikaaro
from registry import get_resource_class


def get_schema(format):
    cls = get_resource_class(format)
    return cls.get_metadata_schema()



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
            properties[name] = Property(value, **parameters)


    def get_property(self, name):
        return self.properties[name]
