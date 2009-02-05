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

# Import from the Standard Library
from datetime import datetime

# Import from itools
from itools.csv import Record, Table as TableFile, Property, is_multilingual
from itools.datatypes import Tokens
from itools.gettext import MSG

# Import from ikaaro
from file import File
from forms import get_default_widget
from resource_ import DBResource
from table_views import Table_View, Table_AddRecord, Table_EditRecord
from table_views import OrderedTable_View



class Table(File):

    class_version = '20081113'
    class_views = ['view', 'add_record', 'edit', 'history']
    class_handler = TableFile
    record_class = Record
    form = []


    def get_schema(self):
        return self.handler.record_schema


    @classmethod
    def get_form(cls):
        if cls.form != []:
            return cls.form
        record_schema = cls.class_handler.record_schema
        return [
            get_default_widget(datatype)(name)
            for name, datatype in record_schema.items() ]


    @classmethod
    def get_field_title(cls, name):
        for widget in cls.form:
            if widget.name == name:
                return getattr(widget, 'title', name)
        return name


    def del_record(self, id):
        self.handler.del_record(id)


    # Views
    new_instance = DBResource.new_instance
    view = Table_View()
    add_record = Table_AddRecord()
    edit_record = Table_EditRecord()


    def update_20081113(self):
        # XXX Hardcoded because too hard to get right.  Maybe changed
        # for specific tables.
        language = 'en'

        handler = self.get_handler()
        schema = handler.record_schema

        handler.set_changed()
        handler.incremental_save = False
        for record in handler.records:
            # XXX Not that versions of deleted records won't be updated.
            # This may be fixed by compacting a table.
            if record is None:
                continue
            for version in record:
                for name in version:
                    if name not in schema:
                        continue
                    datatype = schema[name]
                    if is_multilingual(datatype):
                        for property in version[name]:
                            property.parameters['language'] = language



###########################################################################
# Ordered Table
###########################################################################
class OrderedTableFile(TableFile):

    schema = {'order': Tokens(default=())}


    def get_record_ids_in_order(self):
        """Return ids sort by order"""
        ordered = self.get_property_value('order') or []
        ordered = [ int(x) for x in ordered ]
        record_ids = list(self.get_record_ids())
        for id in ordered:
            if id in record_ids:
                yield id
        # Unordered
        ordered_set = set(ordered)
        for id in record_ids:
            if id not in ordered_set:
                yield id


    def get_records_in_order(self):
        for id in self.get_record_ids_in_order():
            yield self.get_record(id)


    def order_up(self, ids):
        order = self.get_record_ids_in_order()
        order = list(order)
        for id in ids:
            index = order.index(id)
            if index > 0:
                order.remove(id)
                order.insert(index - 1, id)
        # Update the order
        order = [ str(x) for x in order ]
        self.update_properties(order=tuple(order))


    def order_down(self, ids):
        order = self.get_record_ids_in_order()
        order = list(order)
        for id in ids:
            index = order.index(id)
            order.remove(id)
            order.insert(index + 1, id)
        # Update the order
        order = [ str(x) for x in order ]
        self.update_properties(order=tuple(order))


    def order_top(self, ids):
        order = self.get_record_ids_in_order()
        order = list(order)
        order = ids + [ id for id in order if id not in ids ]
        # Update the order
        order = [ str(x) for x in order ]
        self.update_properties(order=tuple(order))


    def order_bottom(self, ids):
        order = self.get_record_ids_in_order()
        order = list(order)
        order = [ id for id in order if id not in ids ] + ids
        # Update the order
        order = [ str(x) for x in order ]
        self.update_properties(order=tuple(order))



class OrderedTable(Table):

    class_title = MSG(u'Ordered Table')
    class_handler = OrderedTableFile

    # Views
    view = OrderedTable_View()

