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
from re import compile
from subprocess import CalledProcessError

# Import from itools
from itools.core import merge_dicts
from itools.datatypes import Boolean, String
from itools.gettext import MSG
from itools.uri import encode_query, get_reference
from itools.web import STLView, ERROR

# Import from ikaaro
from buttons import Button
from metadata import Metadata
from views import BrowseForm



def get_colored_diff(diff):
    """Turn a diff source into a namespace for HTML display.
    """
    # Constants
    password_re = compile('password:(.*)')
    password_old_re = compile('<password>(.*)</password>')

    # Pre-process input: skip until the first diff block
    if diff[:5] != 'diff':
        i = diff.find('\ndiff ')
        diff = diff[i+1:]
    lines = diff.splitlines()

    # Build and return the namespace
    changes = []
    index = -1 # The anchor index to link from the diff stat
    for line in lines:
        # 1. The header
        if line[:5] == 'diff ':
            index += 1
            changes.append({'header': line, 'index': index, 'blocks': []})
            continue

        # 2. Skip some unwanted info
        if line[:6] == 'index ' or line[:3] in ('---', '+++', '@@ '):
            continue

        # 3. The diff
        # For security, hide password the of metadata files
        line = password_re.sub('password:***', line)
        line = password_old_re.sub('<password>***</password>', line)
        # Add the line
        css = {'-': 'rem', '+': 'add'}.get(line[0], None)
        blocks = changes[-1]['blocks']
        if blocks and blocks[-1]['css'] == css:
            blocks[-1]['value'] += '\n'
            blocks[-1]['value'] += line
        else:
            blocks.append({'css': css, 'value': line})

    return changes



def get_colored_stat(stat):
    """Turn a diff stat into a namespace for HTML display"""
    table = []
    for line in stat.splitlines():
        if '|' in line:
            # File change
            filename, change = [x.strip() for x in line.split('|')]
            nlines, change = change.split(' ', 1)
            if '->' in change:
                # Binary change
                before, after = change.split('->')
            else:
                # Text change
                before = change.strip('+')
                after = change.strip('-')
            table.append({'value': filename, 'nlines': nlines,
                'before': before, 'after': after})
        else:
            # Last line of summary
            summary = line
    return {
        'table': table,
        'summary': summary}



def get_older_state(resource, revision, context):
    """All-in-one to get an older metadata and handler state."""
    # Heuristic to remove the database prefix
    prefix = len(str(context.server.target)) + len('/database/')

    # Metadata
    database = context.database
    path = resource.metadata.key[prefix:]
    metadata = database.get_blob_by_revision_and_path(revision, path, Metadata)

    # Handler
    path = resource.handler.key[prefix:]
    cls = resource.handler.__class__
    try:
        handler = database.get_blob_by_revision_and_path(revision, path, cls)
    except CalledProcessError:
        # Phantom handler or renamed file
        handler = None

    return metadata, handler



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

        if to is None:
            # Case 1: show one commit
            try:
                metadata = database.get_diff(revision)
            except CalledProcessError, e:
                error = unicode(str(e), 'utf_8')
                context.message = ERROR(u"Git failed: {error}", error=error)
                return {'metadata': None, 'stat': None, 'changes': None}
            author_name = metadata['author_name']
            metadata['author_name'] = root.get_user_title(author_name)
            stat = database.get_stats(revision)
            diff = metadata['diff']
        else:
            # Case 2: show a set of commits
            metadata = None
            # Get the list of commits affecting the resource
            revisions = [
                x['revision'] for x in resource.get_revisions(content=True) ]
            # Filter revisions in our range
            # Below
            while revisions and revisions[-1] != revision:
                revisions.pop()
            if not revisions:
                error = ERROR(u'Commit {commit} not found', commit=revision)
                context.message = error
                return {'metadata': None, 'stat': None, 'changes': None}
            # Above
            if to != 'HEAD':
                while revisions and revisions[0] != to:
                    revisions.pop(0)
                if not revisions:
                    error = ERROR(u'Commit {commit} not found', commit=to)
                    context.message = error
                    return {'metadata': None, 'stat': None, 'changes': None}
            # Get the list of files affected in this series
            files = database.get_files_affected(revisions)
            # Get the statistic for these files
            # Starting revision is included in the diff
            revision = "%s^" % revision
            stat = database.get_stats(revision, to, paths=files)

            # Reuse the list of files to limit diff produced
            diff = database.get_diff_between(revision, to, paths=files)

        # Ok
        return {
            'metadata': metadata,
            'stat': get_colored_stat(stat),
            'changes': get_colored_diff(diff)}
