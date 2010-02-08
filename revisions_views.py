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
from itools.uri import encode_query, get_reference
from itools.web import STLView

# Import from ikaaro
from buttons import Button
from views import BrowseForm


def get_changes(diff):
    """Turn a diff source into a list of changes for HTML display"""
    changes = []
    password_re = compile('<password>(.*)</password>')
    for line in diff.splitlines():
        if line[:5] == 'index' or line[:3] in ('---', '+++', '@@ '):
            continue
        css = None
        is_header = (line[:4] == 'diff')
        if not is_header:
            if line:
                # For security, hide password the of metadata files
                line = sub(password_re, '<password>***</password>', line)
                if line[0] == '-':
                    css = 'rem'
                elif line[0] == '+':
                    css = 'add'
        # Add the line
        changes.append({'css': css, 'value': line, 'is_header': is_header})
    return changes



class IndexRevision(String):

    @staticmethod
    def decode(data):
        index, revision = data.split('_')
        return int(index), revision


    @staticmethod
    def encode(value):
        raise NotImplementedError



class DiffButton(Button):
    access = 'is_allowed_to_edit'
    name = 'diff'
    title = MSG(u"Diff between selected revisions")
    css = 'button-compare'



class DBResource_CommitLog(BrowseForm):

    access = 'is_allowed_to_edit'
    title = MSG(u"Commit Log")

    schema = {
        'ids': IndexRevision(multiple=True, mandatory=True),
    }
    query_schema = merge_dicts(BrowseForm.query_schema,
                               sort_by=String(default='date'),
                               reverse=Boolean(default=True))

    table_columns = [
        ('checkbox', None),
        ('date', MSG(u'Last Change')),
        ('username', MSG(u'Author')),
        ('message', MSG(u'Comment')),
    ]
    table_actions = [DiffButton]


    def get_items(self, resource, context):
        root = context.root
        items = resource.get_revisions(content=True)
        for i, item in enumerate(items):
            item['username'] = root.get_user_title(item['username'])
            # Hint to sort revisions quickly
            item['index'] = i
        return items


    def sort_and_batch(self, resource, context, results):
        start = context.query['batch_start']
        size = context.query['batch_size']
        sort_by = context.query['sort_by']
        reverse = context.query['reverse']

        # Do not give a traceback if 'sort_by' has an unexpected value
        if sort_by not in [ x[0] for x in self.table_columns ]:
            sort_by = self.query_schema['sort_by'].default

        # Sort & batch
        results.sort(key=itemgetter(sort_by), reverse=reverse)
        return results[start:start+size]


    def get_item_value(self, resource, context, item, column):
        if column == 'checkbox':
            return ('%s_%s' % (item['index'], item['revision']), False)
        elif column == 'date':
            return (item['date'], './;changes?revision=%s' % item['revision'])
        return item[column]


    def action_diff(self, resource, context, form):
        # Take newer and older revisions, even if many selected
        ids = sorted(form['ids'])
        revision = ids.pop()[1]
        to = ids and ids.pop(0)[1] or 'HEAD'
        # FIXME same hack than rename to call a GET from a POST
        query = encode_query({'revision': revision, 'to': to})
        uri = '%s/;changes?%s' % (context.get_link(resource), query)
        return get_reference(uri)



class DBResource_Changes(STLView):

    access = 'is_admin'
    title = MSG(u'Changes')
    template = '/ui/revisions/changes.xml'

    query_schema = {
        'revision': String(mandatory=True),
        'to': String,
        }

    def get_namespace(self, resource, context):
        revision = context.query['revision']
        to = context.query['to']
        root = context.root
        database = context.database

        namespace = {}
        if to is None:
            # Get commit namespace
            metadata = database.get_diff(revision)
            author_name = metadata['author_name']
            metadata['author_name'] = root.get_user_title(author_name)
            namespace['metadata'] = metadata
            namespace['stat'] = database.get_diff_between(revision,
                    to='%s^' % revision, stat=True)
            namespace['changes'] = get_changes(metadata['diff'])
        else:
            # Get diff namespace
            namespace['metadata'] = None
            namespace['stat'] = database.get_diff_between(revision,
                    to, stat=True)
            diff = database.get_diff_between(revision, to)
            namespace['changes'] = get_changes(diff)

        # Ok
        return namespace



# FIXME For backwards compatibility with 0.60.0 to 0.60.7
DBResource_LastChanges = DBResource_CommitLog
