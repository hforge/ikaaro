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
from itools.core import merge_dicts, thingy_lazy_property
from itools.datatypes import Boolean, String
from itools import git
from itools.gettext import MSG
from itools.web import STLView

# Import from ikaaro
from forms import TextField
from views import BrowseForm


class DBResource_LastChanges(BrowseForm):

    access = 'is_allowed_to_view'
    view_title = MSG(u"Last Changes")

    sort_by = BrowseForm.sort_by()
    sort_by.datatype = String(default='date')

    reverse = BrowseForm.reverse()
    reverse.datatype = Boolean(default=True)


    table_columns = [
        ('date', MSG(u'Last Change')),
        ('username', MSG(u'Author')),
        ('message', MSG(u'Comment'))]


    @thingy_lazy_property
    def all_items(self):
        items = self.resource.get_revisions(content=True)
        for item in items:
            item['username'] = self.context.get_user_title(item['username'])
        return items


    @thingy_lazy_property
    def items(self):
        start = self.batch_start.value
        size = self.batch_size.value
        sort_by = self.sort_by.value
        reverse = self.reverse.value

        # Do not give a traceback if 'sort_by' has an unexpected value
        if sort_by not in [ x[0] for x in self.table_columns ]:
            sort_by = self.query_schema['sort_by'].default

        # Sort & batch
        items = sorted(self.all_items, key=itemgetter(sort_by), reverse=reverse)
        return items[start:start+size]


    def get_item_value(self, item, column):
        if column == 'date':
            return (item['date'], './;changes?revision=%s' % item['revision'])
        return item[column]



class DBResource_Changes(STLView):

    access = 'is_admin'
    view_title = MSG(u'Changes')
    template = 'revisions/changes.xml'


    revision = TextField(source='query', datatype=String, required=True)


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
