# -*- coding: UTF-8 -*-
# Copyright (C) 2018 Sylvain Taverne <taverne.sylvain@gmail.com>
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

# Import from standard library
from copy import deepcopy

# Import from itools
from itools.core import merge_dicts, is_prototype, proto_property
from itools.database import AndQuery, NotQuery, OrQuery, PhraseQuery, TextQuery
from itools.datatypes import Boolean, Integer, String
from itools.gettext import MSG
from itools.stl import stl
from itools.web import get_context

# Import from ikaaro
from ikaaro.autoform import AutoForm
from ikaaro.buttons import SearchButton
from ikaaro.fields import Field, Char_Field
from ikaaro.utils import get_base_path_query

# Import from here
from folder_views import Folder_BrowseContent


class AutoTable(Folder_BrowseContent):

    # Base configuration
    template = '/ui/ikaaro/views/autotable/browse.xml'
    prefix = ''
    depth = None
    base_classes = ('folder',)
    base_path_from_resource = True

    # Search configuration
    search_title = None
    search_fields = []
    search_buttons = [SearchButton]

    # Template with column css
    table_template = '/ui/ikaaro/views/autotable/browse_table.xml'
    table_fields = []
    table_actions = []

    # Empty table
    empty_table_template = '/ui/ikaaro/views/autotable/empty_table_template.xml'
    empty_table_msg = MSG(u'No items in the list')

    # Table id / css
    search_form_id = 'form-search'
    search_form_css = ''
    table_form_id = 'form-table'
    table_css = 'table table-striped table-bordered'

    # Sort configuration
    sort_by = None
    sort_reverse = False
    sort_by_key = 'sort_by'
    sort_reverse_key = 'reverse'
    batch_start_key = 'batch_start'
    batch_size_key = 'batch_size'

    # Query_schema
    query_schema = merge_dicts(
        Folder_BrowseContent.query_schema,
        batch_size=Integer(default=50))

    # Base table fields
    name = Char_Field(title=MSG(u'Name'))
    class_title = Char_Field(title=MSG(u'Type'))


    @proto_property
    def search_schema(self):
        schema = {}
        for name in self.search_fields:
            field = self.get_search_field(name)
            if field:
                field = field(multilingual=False)
                schema[name] = field.get_datatype()
                # Force search field not to be mandatory
                schema[name].mandatory = False
        return schema


    def get_search_field(self, name):
        # Get field from view
        field = getattr(self, name, None)
        if field is not None and is_prototype(field, Field):
            return field
        # Get field from base_classes
        class_id = self.base_classes[0]
        context = get_context()
        cls = context.database.get_resource_class(class_id)
        return cls.get_field(name)


    @proto_property
    def search_widgets(self):
        widgets = []
        for name in self.search_fields:
            field = self.get_search_field(name)
            if field:
                field = field(multilingual=False)
                widget = field.get_widget(name)
                widgets.append(widget)
        return widgets


    def get_query_schema(self):
        proxy = super(AutoTable, self)
        kw = {}
        for key, value in proxy.get_query_schema().iteritems():
            # Fix sort and batch if CompositeView with self.prefix
            if self.prefix:
                if key in self.sort_by_key:
                    kw[self.sort_by_key] = String(default=self.sort_by)
                elif key in self.sort_reverse_key:
                    kw[self.sort_reverse_key] = Boolean(
                        default=self.sort_reverse)
                elif key in self.batch_start_key:
                    kw[self.batch_start_key] = value
                elif key in self.batch_size_key:
                    kw[self.batch_size_key] = value
                else:
                    kw[key] = value
            # Fix default value of sort_by and sort_reverse (inherited)
            if (key == 'sort_by' and \
                    getattr(self, 'sort_by', None) is not None):
                kw['sort_by'] = String(default=self.sort_by)
            elif (key == 'reverse' and \
                    getattr(self, 'sort_reverse', None) is not None):
                kw['reverse'] = Boolean(default=self.sort_reverse)
            elif (key == 'reverse' and \
                    getattr(self, 'reverse', None) is not None):
                kw['reverse'] = Boolean(default=self.reverse)
            else:
                kw[key] = value
        return kw


    def get_field(self, name):
        # Get field from view
        field = getattr(self, name, None)
        if field is not None and is_prototype(field, Field):
            return field
        # Get field from base_classes
        class_id = self.base_classes[0]
        context = get_context()
        cls = context.database.get_resource_class(class_id)
        return cls.get_field(name)


    def get_table_columns(self, resource, context):
        columns = []
        for name in self.table_fields:
            if name == 'checkbox':
                columns.append(('checkbox', None))
                continue

            if name == 'name':
                columns.append((name, MSG(u'ID')))
            else:
                field = self.get_field(name)
                if field:
                    stored = '.' not in name and field.stored
                    if hasattr(field, 'table_title'):
                        title = field.table_title
                    else:
                        title = field.title
                    if hasattr(field, 'is_available'):
                        if not field.is_available(context):
                            continue
                    columns.append((name, title, stored))

        return columns


    def get_search_namespace(self, resource, context):
        buttons = deepcopy(self.search_buttons)
        form = AutoForm(
            form_id=self.search_form_id,
            form_css=self.search_form_css,
            template=self.search_template,
            template_field=self.search_template_field,
            title=self.search_title,
            method='get',
            schema=self.search_schema,
            widgets=self.search_widgets,
            actions=buttons)
        return form.GET(resource, context)


    def get_table_namespace(self, resource, context, items):
        """Add css to columns."""
        # (1) Actions (submit buttons)
        self._items = items
        actions = self.actions_namespace
        # (2) Table Head: columns
        table_head = self.get_table_head(resource, context, items)

        # (3) Table Body: rows
        columns = self.get_table_columns(resource, context)
        rows = []
        for item in items:
            row_columns = []
            for column in columns:
                column = column[0]
                # Skip the checkbox column if there are not any actions
                if column == 'checkbox':
                    if not self.external_form and not actions:
                        continue

                value = self.get_item_value(resource, context, item, column)
                column_ns = {
                    'is_checkbox': False,
                    'is_icon': False,
                    'is_link': False,
                    'css': self.get_column_css(resource, context, column),
                }
                # Type: empty
                if value is None:
                    pass
                # Type: checkbox
                elif column == 'checkbox':
                    value, checked = value
                    column_ns['is_checkbox'] = True
                    column_ns['value'] = value
                    column_ns['checked'] = checked
                # Type: icon
                elif column == 'icon':
                    column_ns['is_icon'] = True
                    column_ns['src'] = value
                # Type: normal
                else:
                    column_ns['is_link'] = True
                    if type(value) is tuple:
                        value, href = value
                    else:
                        href = None
                    column_ns['value'] = value
                    column_ns['href'] = href
                row_columns.append(column_ns)
            # Row css
            row_css = self.get_item_value(resource, context, item, 'row_css')

            # Append
            rows.append({'css': row_css, 'columns': row_columns})

        # Ok
        return {
            'css': self.table_css,
            'form_id': self.table_form_id,
            'columns': table_head,
            'rows': rows,
            'actions': actions,
            'external_form': self.external_form or not actions}


    def get_column_css(self, resource, context, column):
        return None


    def add_to_search_query(self, resource, context, key, value, datatype):
        """ Permet de spécifier la query à utiliser pour "key"."""
        if key == 'searchable_title':
            squery = [ PhraseQuery('searchable_title', x)
                        for x in value.split(' ') ]
            squery = squery[0] if len(squery) == 1 else AndQuery(*squery)
            return squery
        # Multiple
        if datatype.multiple is True:
            query = OrQuery(*[ PhraseQuery(key, x) for x in value ])
        # Singleton
        else:
            if value is False:
                # FIXME No value means False in xapian
                query = NotQuery(PhraseQuery(key, True))
            else:
                query = PhraseQuery(key, value)
        return query


    def get_search_query(self, resource, context):
        """ On surcharge pour utiliser "add_to_search_query"."""
        query = []
        form = context.query
        for key, datatype in self.search_schema.items():
            value = form[key]
            if value is None or value == '' or value == []:
                continue
            # Special case: search on text, title and name AS AndQuery
            if key == 'text':
                text_query = []
                value = value.split(' ')
                for v in value:
                    t_query = OrQuery(TextQuery('title', v),
                                      TextQuery('text', v),
                                      PhraseQuery('name', v))
                    text_query.append(t_query)
                if len(text_query) == 1:
                    text_query = text_query[0]
                else:
                    text_query = AndQuery(*text_query)
                query.append(text_query)
            # Special case: type
            elif key == 'format':
                squery = [ PhraseQuery('format', x) for x in value.split(',') ]
                squery = squery[0] if len(squery) == 1 else OrQuery(*squery)
                query.append(squery)
            else:
                sub_query = self.add_to_search_query(resource, context, key, value, datatype)
                if sub_query:
                    query.append(sub_query)
        if len(query) == 1:
            return query[0]
        elif len(query) > 1:
            return AndQuery(*query)
        return query



    def get_items(self, resource, context):
        query = self.get_items_query(resource, context)
        search_query = self.get_search_query(resource, context)
        if search_query:
            query = AndQuery(query, search_query)
        return context.search(query)


    def get_items_query(self, resource, context):
        query = None
        if self.base_path_from_resource:
            # Search in subtree
            query = get_base_path_query(resource.abspath, max_depth=self.depth)

        # Base classes
        base_classes = self.base_classes
        if base_classes is not None:
            base_classes_query = [ PhraseQuery('base_classes', x)
                                    for x in base_classes ]
            if len(base_classes_query) == 1:
                base_classes_query = base_classes_query[0]
            else:
                base_classes_query = OrQuery(*base_classes_query)
            if query:
                query = AndQuery(query, base_classes_query)
            else:
                query = base_classes_query

        # Exclude non-content
        if self.search_content_only(resource, context) is True:
            if query:
                query = AndQuery(query, PhraseQuery('is_content', True))
            else:
                query = PhraseQuery('is_content', True)
        return query


    def search_content_only(self, resource, context):
        return False


    def get_item_value(self, resource, context, item, column):
        if type(item) is tuple:
            brain, item_resource = item
        else:
            item_resource = item
        # Default columns
        if column == 'name':
            name = item_resource.name
            return name, context.get_link(item_resource)
        elif column == 'checkbox':
            # checkbox
            parent = item.parent
            if parent is None:
                return None
            if item.name in parent.__fixed_handlers__:
                return None
            resource_id = str(item.abspath)
            return resource_id, False
        elif column == 'title':
            return item_resource.get_title(), context.get_link(item_resource)
        elif column == 'link':
            return context.get_link(item_resource)
        elif column == 'class_title':
            return item_resource.class_title.gettext()
        # Default
        value = item.get_value_title(column)
        if value:
            return value
        return None


    def get_before_namespace(self, resource, context):
        return None


    def get_after_namespace(self, resource, context):
        return None


    def get_namespace(self, resource, context):
        tables = []
        batch = None
        table = None
        # Batch
        items = self.get_items(resource, context)
        if items:
            if self.batch is not None:
                total = len(items)
                batch = self.batch(context=context, total=total).render()

            # Content
            items = self.sort_and_batch(resource, context, items)
            if self.table_template is not None:
                template = context.get_template(self.table_template)
                ns_table = self.get_table_namespace(resource, context, items)
                ns_table['is_last_table'] = True
                table = stl(template, ns_table)
        else:
            ns_empty_table = {'msg': self.empty_table_msg}
            template = context.get_template(self.empty_table_template)
            table = stl(template, ns_empty_table)
        # The Search Form
        search = None
        if self.search_widgets:
            search = self.get_search_namespace(resource, context)
        # Batch, table, search
        namespace = {}
        namespace['batch'] = batch
        namespace['table'] = table
        namespace['tables'] = tables
        namespace['search'] = search
        # Before and after
        namespace['before'] = self.get_before_namespace(resource, context)
        namespace['after'] = self.get_after_namespace(resource, context)
        # Ok
        return namespace


    action_remove_goto = None
    def action_remove(self, resource, context, form):
        proxy = super(AutoTable, self)
        ret = proxy.action_remove(resource, context, form)
        # action_remove_goto
        if self.action_remove_goto:
            message = context.message
            if type(message) is list:
                message = MSG(u'\n'.join([x.gettext() for x in message]))
            return context.come_back(message, goto=self.action_remove_goto)
        # Ok
        return ret
