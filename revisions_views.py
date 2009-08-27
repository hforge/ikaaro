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
from itools.core import merge_dicts
from itools.datatypes import Boolean, String
from itools import git
from itools.gettext import MSG
from itools.web import STLView

# Import from ikaaro
from views import BrowseForm


class DBResource_LastChanges(BrowseForm):


    access = 'is_allowed_to_view'
    title = MSG(u"Last Changes")

    query_schema = merge_dicts(BrowseForm.query_schema,
                               sort_by=String(default='date'),
                               reverse=Boolean(default=True))


    table_columns = [
        ('date', MSG(u'Last Change')),
        ('username', MSG(u'Author')),
        ('message', MSG(u'Comment'))]


    def get_items(self, resource, context):
        items = resource.get_revisions(content=True)
        for item in items:
            item['username'] = context.get_user_title(item['username'])
        return items


    def sort_and_batch(self, resource, context, results):
        start = context.get_query_value('batch_start')
        size = context.get_query_value('batch_size')
        sort_by = context.get_query_value('sort_by')
        reverse = context.get_query_value('reverse')

        # Do not give a traceback if 'sort_by' has an unexpected value
        if sort_by not in [ x[0] for x in self.table_columns ]:
            sort_by = self.query_schema['sort_by'].default

        # Sort & batch
        results.sort(key=itemgetter(sort_by), reverse=reverse)
        return results[start:start+size]


    def get_item_value(self, resource, context, item, column):
        if column=='date':
            return (item['date'], './;changes?revision=%s' % item['revision'])
        return item[column]



class DBResource_Changes(STLView):

    access = 'is_admin'
    title = MSG(u'Changes')
    template = 'revisions/changes.xml'

    query_schema = {
        'revision': String(mandatory=True)}

    def get_namespace(self, resource, context):
        revision = context.query['revision']

        # Get the revision data
        namespace = context.database.get_diff(revision)
        author_name = namespace['author_name']
        namespace['author_name'] = context.get_user_title(author_name)

        # Diff
        changes = []
        password_re = compile('<password>(.*)</password>')
        for line in namespace['diff'].splitlines():
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
        namespace['changes'] = changes

        # Ok
        return namespace
