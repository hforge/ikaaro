# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Luis Arturo Belmar-Letelier <luis@itaapy.com>
# Copyright (C) 2007 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
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

# Import from the Standard Library
from operator import itemgetter

# Import from itools
from itools.csv import Table as BaseTable
from itools.datatypes import Boolean, Integer, Unicode
from itools.gettext import MSG
from itools.xapian import EqQuery, AndQuery
from itools.xml import XMLParser

# Import from ikaaro
from ikaaro.forms import TextWidget, BooleanCheckBox
from ikaaro.registry import register_object_class
from ikaaro.table import Table, TableView


###########################################################################
# Views
###########################################################################
class SelectTableView(TableView):

    def get_table_columns(self, resource, context):
        columns = TableView.get_table_columns(self, resource, context)
        columns.append(('issues', u'Issues'))
        return columns


    def get_item_value(self, resource, context, item, column):
        if column == 'issues':
            # Append a column for the number of issues
            root = context.root
            abspath = resource.parent.get_canonical_path()
            base_query = AndQuery(
                            EqQuery('parent_path', str(abspath)),
                            EqQuery('format', 'issue'))
            search_query = AndQuery(base_query, EqQuery(filter, id))
            results = root.search(search_query)
            count = len(results)
            if count == 0:
                return 0
            return count, '../;view?%s=%s' % (filter, id)

        return TableView.get_item_value(self, resource, context, item, column)



###########################################################################
# Resources
###########################################################################
class SelectTableTable(BaseTable):

    schema = {'title': Unicode}


class SelectTable(Table):

    class_id = 'tracker_select_table'
    class_version = '20071216'
    class_title = MSG(u'Select Table')
    class_handler = SelectTableTable

    form = [TextWidget('title', title=u'Title')]


    def get_options(self, value=None, sort='title'):
        table = self.handler
        options = []
        for x in table.get_records():
            ns = {'id': x.id, 'title': x.title}
            if sort == 'rank':
                ns['rank'] = x.get_value('rank')
            options.append(ns)

        if sort is not None:
            options.sort(key=lambda x: x.get(sort))
        # Set 'is_selected'
        if value is None:
            for option in options:
                option['is_selected'] = False
        elif isinstance(value, list):
            for option in options:
                option['is_selected'] = (option['id'] in value)
        else:
            for option in options:
                option['is_selected'] = (option['id'] == value)

        return options


    view = SelectTableView()


    def del_record_action(self, context):
        # check input
        ids = context.get_form_values('ids', type=Integer)
        if not ids:
            return context.come_back(MSG(u'No objects selected.'))

        filter = self.name[:-1]
        if self.name.startswith('priorit'):
            filter = 'priority'
        root = context.root
        abspath = self.parent.get_canonical_path()

        # Search
        base_query = EqQuery('parent_path', str(abspath))
        base_query = AndQuery(base_query, EqQuery('format', 'issue'))
        removed = []
        for id in ids:
            query = AndQuery(base_query, EqQuery(filter, id))
            count = root.search(query).get_n_documents()
            if count == 0:
                self.handler.del_record(id)
                removed.append(str(id))

        message = u'Objects removed: $objects.'
        return context.come_back(message, objects=', '.join(removed))




class OrderedSelectTableTable(SelectTableTable):

    schema = {'title': Unicode, 'rank': Integer(index='keyword', unique=True)}


class OrderedSelectTable(SelectTable):

    class_id = 'tracker_ordered_select_table'
    class_version = '20080415'
    class_title = MSG(u'Ordered select table')
    class_handler = OrderedSelectTableTable

    form = [TextWidget('title', title=u'Title'),
            TextWidget('rank', title=u'Rank', mandatory=True)]



class VersionsTable(BaseTable):

    schema = {'title': Unicode(),
              'released': Boolean()}


class Versions(SelectTable):

    class_id = 'tracker_versions'
    class_version = '20071216'
    class_handler = VersionsTable

    form = [TextWidget('title', title=u'Title'),
            BooleanCheckBox('released', title=u'Released')]



###########################################################################
# Register
###########################################################################
register_object_class(SelectTable)
register_object_class(OrderedSelectTable)
register_object_class(Versions)
