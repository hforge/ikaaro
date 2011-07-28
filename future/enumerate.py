# -*- coding: UTF-8 -*-
# Copyright (C) 2009 Hervé Cauwelier <herve@itaapy.com>
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
from itools.datatypes import Enumerate
from itools.gettext import MSG
from itools.web import get_context

# Import from ikaaro
from ikaaro.autoform import title_widget
from ikaaro.datatypes import Multilingual
from ikaaro.table import OrderedTableFile, OrderedTable



class EnumerateTableFile(OrderedTableFile):

    record_properties = {
        'title': Multilingual(mandatory=True)}



class EnumerateTable(OrderedTable):

    class_id = 'EnumerateTable'
    class_title = MSG(u"Enumerate")
    class_handler = EnumerateTableFile

    form = [title_widget]



class TableEnumerate(Enumerate):

    table_path = 'path/relative/to/site_root'


    def get_options(cls):
        table = get_context().root.get_resource(cls.table_path)
        handler = table.handler
        options = []
        for record in handler.get_records_in_order():
            title = handler.get_record_value(record, 'title')
            if not title:
                title = handler.get_record_value(record, 'title')
            options.append({'name': str(record.id), 'value': title})
        return options

