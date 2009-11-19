# -*- coding: UTF-8 -*-
# Copyright (C) 2009 Sylvain Taverne <sylvain@itaapy.com>
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
from operator import itemgetter
from re import compile, sub

# Import from itools
from itools.core import thingy_property, thingy_lazy_property
from itools.core import OrderedDict
from itools.datatypes import Boolean, String
from itools.gettext import MSG
from itools.web import stl_view, hidden_field, make_stl_template

# Import from ikaaro
from views import Container_Search, Container_Sort, Container_Batch
from views import Container_Table


class DBResource_LastChanges(stl_view):

    access = 'is_allowed_to_view'
    view_title = MSG(u"Last Changes")

    template = make_stl_template("${batch}${table}")


    # Search
    @thingy_lazy_property
    def items(self):
        view = self.view
        items = view.resource.get_revisions(content=True)
        for item in items:
            item['username'] = view.context.get_user_title(item['username'])
        return items

    search = Container_Search()
    search.items = items

    # Sort
    @thingy_lazy_property
    def items(self):
        sort_by = self.sort_by.value
        reverse = self.reverse.value

        # (FIXME) Do not give a traceback if 'sort_by' has an unexpected value
        if sort_by not in self.sort_by.values:
            sort_by = self.sort_by.default

        # Sort & batch
        key = itemgetter(sort_by)
        return sorted(self.view.search.items, key=key, reverse=reverse)

    sort = Container_Sort()
    sort.sort_by = sort.sort_by(value='date')
    sort.sort_by.values = OrderedDict([
        ('date', {'title': MSG(u'Last Change')}),
        ('username', {'title': MSG(u'Author')}),
        ('message', {'title': MSG(u'Comment')})])
    sort.reverse = sort.reverse(value=True)
    sort.items = items

    # Batch
    @thingy_lazy_property
    def items(self):
        start = self.batch_start.value
        size = self.batch_size.value
        return self.view.sort.items[start:start+size]

    batch = Container_Batch()
    batch.items = items

    # Table
    @thingy_property
    def header(self):
        return [
            (k, v['title'], True)
            for k, v in self.root_view.sort.sort_by.values.items() ]

    table = Container_Table()
    table.header = header


    def get_item_value(self, item, column):
        if column == 'date':
            return (item['date'], './;changes?revision=%s' % item['revision'])
        return item[column]



class DBResource_Changes(stl_view):

    access = 'is_admin'
    view_title = MSG(u'Changes')
    template = 'revisions/changes.xml'


    revision = hidden_field(source='query', required=True)


    @thingy_lazy_property
    def diff(self):
        revision = self.revision.value
        return self.context.database.get_diff(revision)


    def author_name(self):
        author_name = self.diff['author_name']
        return self.context.get_user_title(author_name)


    def author_date(self):
        return self.diff['author_date']


    def subject(self):
        return self.diff['subject']


    def changes(self):
        # Diff
        changes = []
        password_re = compile('<password>(.*)</password>')
        for line in self.diff['diff'].splitlines():
            if line[:5] == 'index' or line[:3] in ('---', '+++', '@@ '):
                continue
            css = None
            is_header = (line[:4] == 'diff')
            if not is_header:
                # For security, hide password the of metadata files
                line = sub(password_re, '<password>***</password>', line)
                if line[0] == '-':
                    css = 'rem'
                elif line[0] == '+':
                    css = 'add'
            # Add the line
            changes.append({'css': css, 'value': line, 'is_header': is_header})
        return changes
