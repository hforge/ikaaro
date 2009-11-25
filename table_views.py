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
from itools.core import thingy_lazy_property
from itools.csv import UniqueError, Property, is_multilingual
from itools.datatypes import Integer, Enumerate, Tokens
from itools.gettext import MSG
from itools.web import INFO, ERROR, FormError
from itools.web import view, stl_view, make_stl_template
from itools.web import readonly_field, multiple_choice_field
from itools.xapian import PhraseQuery

# Import from ikaaro
from autoform import AutoForm, get_default_field
from buttons import RemoveButton, OrderUpButton, OrderDownButton
from buttons import OrderBottomButton, OrderTopButton
from messages import MSG_CHANGES_SAVED
from resource_views import EditLanguageMenu
from views import Container_Batch, Container_Sort, Container_Search
from views import Container_Form, Container_Table


class TableResource_Search(Container_Search):

    @thingy_lazy_property
    def items(self):
        items = self.resource.handler.get_records()
        return list(items)



class TableResource_Sort(Container_Sort):

    @thingy_lazy_property
    def items(self):
        items = self.view.search.items

        sort_by = self.sort_by.value
        if sort_by:
            reverse = self.reverse.value
            get_value = self.resource.handler.get_record_value
            items.sort(key=lambda x: get_value(x, sort_by), reverse=reverse)

        return items



class TableResource_Batch(Container_Batch):

    @thingy_lazy_property
    def items(self):
        items = self.view.sort.items

        # Batch
        start = self.batch_start.value
        size = self.batch_size.value
        if size > 0:
            return items[start:start+size]
        return items[start:]



class ids_field(multiple_choice_field):

    datatype = Integer
    required = True

    @thingy_lazy_property
    def values(self):
        values = self.view.resource.handler.get_record_ids()
        return set(values)



class TableResource_Table(Container_Table):

    ids = ids_field()

    def get_table_columns(self):
        columns = [
            ('checkbox', None, False),
            ('id', MSG(u'id'), True)]

        # From the schema
        return columns + [
            (name, name, True)
            for name, datatype in self.resource.get_schema().iteritems() ]



class TableResource_View(stl_view):

    access = 'is_allowed_to_view'
    access_POST = 'is_allowed_to_edit'
    view_title = MSG(u'View')
    icon = 'view.png'

    template = make_stl_template("${batch}${form}")

    search = TableResource_Search
    sort = TableResource_Sort
    batch = TableResource_Batch

    form = Container_Form()
    form.content = TableResource_Table()
    form.actions = [RemoveButton]


    def get_item_value(self, item, column):
        if column == 'checkbox':
            return item.id, False
        elif column == 'id':
            id = item.id
            return id, '%s/;edit_record?id=%s' % (self.resource.path, id)

        # Columns
        handler = self.resource.handler
        value = handler.get_record_value(item, column)
        datatype = handler.get_record_datatype(column)

        # Multilingual
        if is_multilingual(datatype):
            return value

        # Multiple
        is_multiple = datatype.multiple
        is_tokens = issubclass(datatype, Tokens)

        if is_multiple or is_tokens:
            if is_multiple:
                value.sort()
            value_length = len(value)
            if value_length > 0:
                value = value[0]
            else:
                value = None

        # Enumerate
        if issubclass(datatype, Enumerate):
            value = datatype.get_value(value)

        return value


    #######################################################################
    # Form Actions
    #######################################################################
    def action_remove(self):
        resource = self.resource
        ids = self.form.content.ids.value
        for id in ids:
            resource.handler.del_record(id)
        # Reindex
        context = self.context
        context.change_resource(resource)
        # Ok
        context.message = INFO(u'Record deleted.')
        context.redirect()



###########################################################################
# Add/Edit records
###########################################################################
class TableResource_AddEditRecord(AutoForm):

    access = 'is_allowed_to_edit'
    context_menus = [EditLanguageMenu()]


    @thingy_lazy_property
    def schema(self):
        return self.resource.get_schema()


    def get_field_names(self):
        return self.schema.keys()


    def get_field(self, name):
        datatype = self.schema[name]
        field = get_default_field(datatype)
        return field(name, title=name)


#   def get_field_title(self, resource, name):
#       for widget in resource.get_form():
#           if widget.name == name:
#               title = getattr(widget, 'title', None)
#               if title:
#                   return title.gettext()
#               return name
#       return name


    def action(self):
        """Code shared by the add & edit actions.  It builds a new record
        from the form.
        """
        language = self.content_language

        # Builds a new record from the form.
        record = {}
        for name, datatype in self.schema.iteritems():
            value = getattr(self, name).value
            if is_multilingual(datatype):
                value = Property(value, language=language)
            elif datatype.multiple:
                # textarea -> string
                if not issubclass(datatype, Enumerate):
                    value = [ x.strip() for x in value.splitlines() ]
                    value = [ datatype.decode(x) for x in value if x ]
            record[name] = value

        # Change
        context = self.context
        try:
            self.action_add_or_edit(record)
        except UniqueError, error:
            title = self.get_field_title(self.resource, error.name)
            context.message = ERROR(str(error), field=title, value=error.value)
        except ValueError, error:
            message = ERROR(u'Error: {msg}', msg=str(error))
            context.message = message
        else:
            return self.action_on_success()



class TableResource_AddRecord(TableResource_AddEditRecord):

    view_title = MSG(u'Add Record')
    icon = 'new.png'
    submit_value = MSG(u'Add')


    def action_add_or_edit(self, record):
        self.resource.handler.add_record(record)
        # Reindex the resource
        self.context.change_resource(self.resource)


    def action_on_success(self):
        resource = self.resource
        context = self.context

        n = len(resource.handler.records) - 1
        context.message = MSG(u'New record added.')
        location = '%s/;edit_record?id=%s' % (resource.path, n)
        context.created(location)



class id_field(readonly_field):

    source = 'query'
    datatype = Integer
    required = True
    title = MSG(u'Id')

    @thingy_lazy_property
    def displayed(self):
        return self.value



class TableResource_EditRecord(TableResource_AddEditRecord):

    view_title = MSG(u'Edit record')
    id = id_field()


    def get_field_names(self):
        field_names = super(TableResource_EditRecord, self).get_field_names()
        field_names.insert(0, 'id')
        return field_names


    def get_field(self, name):
        field = super(TableResource_EditRecord, self).get_field(name)
        # The value
        id = self.id.value
        handler = self.resource.get_handler()
        record = handler.get_record(id)
        field.value = handler.get_record_value(record, name)
        # Ok
        return field


    def cook(self, method):
        super(TableResource_EditRecord, self).cook(method)
        id = self.id.value
        if id is None:
            msg = MSG(u'The "{id}" record is missing.')
            raise FormError, msg.gettext(id=self.id.raw_value)

        record = self.resource.get_handler().get_record(id)
        if record is None:
            msg = MSG(u'The "{id}" record is missing.')
            raise FormError, msg.gettext(id=id)


    def get_title(self, context):
        id = self.id.value
        return self.title.gettext(id=id)


    def action_add_or_edit(self, record):
        id = self.id.value
        self.resource.handler.update_record(id, **record)
        # Reindex the resource
        self.context.change_resource(self.resource)


    def action_on_success(self):
        context = self.context
        context.message = MSG_CHANGES_SAVED
        context.redirect()



##########################################################################
# Ordered Views
##########################################################################

class OrderedTableResource_Sort(TableResource_Sort):

    @thingy_lazy_property
    def items(self):
        sort_by = self.sort_by.value
        if sort_by == 'order':
            reverse = self.reverse.value
            ordered_ids = self.resource.handler.get_record_ids_in_order()
            ordered_ids = list(ordered_ids)
            key = lambda x: ordered_ids.index(x.id)
            return sorted(self.view.search.items, key=key, reverse=reverse)

        return super(OrderedTableResource_Sort, self).items



class OrderedTableResource_Table(TableResource_Table):

    def get_table_columns(self):
        columns = super(OrderedTableResource_Table, self).get_table_columns()
        columns.append(('order', MSG(u'Order'), True))
        return columns



class OrderedTableResource_View(TableResource_View):

    search = TableResource_View.search()

    @thingy_lazy_property
    def search__items(self):
        items = self.resource.handler.get_records_in_order()
        return list(items)


    sort = OrderedTableResource_Sort()

    form = TableResource_View.form()
    form.content = OrderedTableResource_Table()
    form.actions = [RemoveButton, OrderUpButton, OrderDownButton,
                    OrderTopButton, OrderBottomButton]


    def get_item_value(self, item, column):
        if column == 'order':
            ordered_ids = list(self.resource.handler.get_record_ids_in_order())
            return ordered_ids.index(item.id) + 1

        parent = super(OrderedTableResource_View, self)
        return parent.get_item_value(item, column)


    ######################################################################
    # Form Actions
    ######################################################################
    def action_order_up(self):
        ids = self.form.content.ids.value
        self.resource.handler.order_up(ids)
        # Ok
        context = self.context
        context.message = INFO(u'Resources ordered up.')
        context.redirect()


    def action_order_down(self):
        ids = self.form.content.ids.value
        self.resource.handler.order_down(ids)
        # Ok
        context = self.context
        context.message = INFO(u'Resources ordered down.')
        context.redirect()


    def action_order_top(self):
        ids = self.form.content.ids.value
        self.resource.handler.order_top(ids)
        # Ok
        context = self.context
        context.message = INFO(u'Resources ordered on top.')
        context.redirect()


    def action_order_bottom(self):
        ids = self.form.content.ids.value
        self.resource.handler.order_bottom(ids)
        # Ok
        context = self.context
        context.message = INFO(u'Resources ordered on bottom.')
        context.redirect()



class TableResource_ExportCSV(view):

    access = 'is_admin'
    view_title = MSG(u"Export to CSV")
    # String to join multiple values (or they will raise an error)
    multiple_separator = None
    # CSV columns separator
    csv_separator = ','


    def get_mtime(self, resource):
        return resource.handler.get_mtime()


    @thingy_lazy_property
    def content_language(self):
        return self.resource.get_content_language()


    def GET(self, resource, context):
        handler = resource.handler
        columns = ['id'] + [widget.name for widget in self.get_form()]
        csv = handler.to_csv(columns, separator=self.multiple_separator,
                             language=self.content_language)

        # Ok
        context.set_content_type('text/comma-separated-values')
        name = resource.get_name()
        context.set_content_disposition('inline', '%s.csv' % name)
        return csv.to_str(separator=self.csv_separator)

