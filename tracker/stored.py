# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Luis Arturo Belmar-Letelier <luis@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2007-2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007-2008 Nicolas Deram <nicolas@itaapy.com>
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
from itools.datatypes import Boolean, Integer, String, Unicode
from itools.gettext import MSG
from itools.handlers import ConfigFile

# Import from ikaaro
from ikaaro.registry import register_resource_class
from ikaaro.text import Text



class StoredSearchFile(ConfigFile):

    schema = {
        'text': Unicode,
        'mtime': Integer(default=0),
        'product': Integer(multiple=True),
        'module': Integer(multiple=True),
        'version': Integer(multiple=True),
        'type': Integer(multiple=True),
        'priority': Integer(multiple=True),
        'assigned_to': String(multiple=True),
        'state': Integer(multiple=True),
        'sort_by': String,
        'reverse': Boolean,
        }


class StoredSearch(Text):

    class_id = 'stored_search'
    class_version = '20071215'
    class_title = MSG(u'Stored Search')
    class_handler = StoredSearchFile


    def get_values(self, name, type=None):
        return self.handler.get_value(name)

    def set_values(self, name, value, type):
        if isinstance(value, list):
            value = [ type.encode(x) for x in value ]
            value = ' '.join(value)
        self.handler.set_value(name, value)




# Register
register_resource_class(StoredSearch)
