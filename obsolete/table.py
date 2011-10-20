# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007-2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007-2008 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2007-2008 Sylvain Taverne <sylvain@itaapy.com>
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
from itools.csv import Record, Table as TableFile
from itools.datatypes import Tokens
from itools.gettext import MSG
from itools.web import get_context

# Import from ikaaro
from ikaaro.autoform import get_default_widget
from ikaaro.fields import File_Field
from ikaaro.file import File
from ikaaro.order import OrderAware
from ikaaro.resource_ import DBResource



class Table(File):

    class_views = ['view', 'add_record', 'edit', 'commit_log']
    record_class = Record
    form = []

    # Fields
    table = File_Field(class_handler=TableFile)


    def get_table(self):
        table = self.get_value('table')
        if table is None:
            table = self.table.class_handler()
            self.set_value('table', table)
        return table

    handler = property(get_table) # XXX Backwards compatibility


    @classmethod
    def get_schema(self):
        return self.table.class_handler.record_properties


    @classmethod
    def get_form(self):
        if self.form:
            return self.form
        schema = self.table.class_handler.record_properties
        return [ get_default_widget(datatype)(name)
                 for name, datatype in schema.items() ]


    def get_record(self, id):
        table = self.get_value('table')
        if table is None:
            return None
        return table.get_record(id)


    def add_new_record(self, record):
        get_context().database.change_resource(self)
        return self.get_table().add_record(record)


    def update_record(self, id, **kw):
        get_context().database.change_resource(self)
        self.get_table().update_record(id, **kw)


    def del_record(self, id):
        get_context().database.change_resource(self)
        self.get_table().del_record(id)


    # Views
    new_instance = DBResource.new_instance



###########################################################################
# Ordered Table
###########################################################################
class OrderedTableFile(TableFile):

    schema = {'order': Tokens}


class OrderedTable(Table, OrderAware):

    class_title = MSG(u'Ordered Table')

    table = Table.table(class_handler=OrderedTableFile)

    allow_to_unorder_items = False

    def update_order(self, order):
        order = [str(x) for x in order]
        table = self.get_value('table')
        table.update_properties(order=tuple(order))


    def get_ordered_values(self):
        table = self.get_value('table')
        ordered = table.get_property_value('order') or []
        ordered = [ int(x) for x in ordered ]
        # Get existing records id (A record should have been deleted)
        record_ids = list(table.get_record_ids())
        for id in ordered:
            if id in record_ids:
                yield id
        # Unordered
        if self.allow_to_unorder_items is False:
            ordered_set = set(ordered)
            for id in record_ids:
                if id not in ordered_set:
                    yield id



    def get_records_in_order(self):
        table = self.get_value('table')
        if table:
            for id in self.get_ordered_values():
                yield table.get_record(id)
