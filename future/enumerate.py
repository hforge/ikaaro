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
from itools.datatypes import Unicode, Enumerate
from itools.gettext import MSG
from itools.http import get_context

# Import from ikaaro
from ikaaro.autoform import title_widget
from ikaaro.table import OrderedTableFile, OrderedTable



class EnumerateTableFile(OrderedTableFile):

    record_properties = {
        'title': Unicode(mandatory=True, multiple=True)}



class EnumerateTable(OrderedTable):

    class_id = 'EnumerateTable'
    class_title = MSG(u"Enumerate")
    class_handler = EnumerateTableFile

    form = [title_widget]



class TableEnumerate(Enumerate):

    table_path = 'path/relative/to/site_root'


    def get_options(cls):
        context = get_context()
        here = context.resource
        table = here.get_site_root().get_resource(cls.table_path)
        handler = table.handler
        language = here.get_content_language(context)
        options = []
        for record in handler.get_records_in_order():
            title = handler.get_record_value(record, 'title', language)
            if not title:
                title = handler.get_record_value(record, 'title')
            options.append({'name': str(record.id), 'value': title})
        return options

