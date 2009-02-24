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
from folder_views import BrowseForm


class Revisions_LastChanges(BrowseForm):


    access = 'is_allowed_to_view'
    title = MSG(u"Last Changes")

    query_schema = merge_dicts(BrowseForm.query_schema,
                               sort_by=String(default='date'),
                               reverse=Boolean(default=True))


    table_columns = [
        ('date', MSG(u'Last Change')),
        ('username', MSG(u'Author')),
        ('message', MSG(u'Comment')),
    ]


    def get_items(self, resource, context):
        root = context.root
        items = resource.get_revisions(context, content=True)
        for item in items:
            item['username'] = root.get_user_title(item['username'])
        return items


    def sort_and_batch(self, resource, context, results):
        start = context.query['batch_start']
        size = context.query['batch_size']
        sort_by = context.query['sort_by']
        reverse = context.query['reverse']

        results.sort(key=itemgetter(sort_by), reverse=reverse)
        return results[start:start+size]


    def get_item_value(self, resource, context, item, column):
        if column=='date':
            return (item['date'], './;changes?revision=%s' % item['revision'])
        return item[column]



class Revisions_Changes(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'Changes')
    template = '/ui/revisions/changes.xml'

    schema = {
        'revision': String(mandatory=True),
        }

    def get_namespace(self, resource, context):
        revision = context.get_form_value('revision')

        # Get the revision data
        database = context.database
        ns = database.get_revision(revision)
        ns['username'] = context.root.get_user_title(ns['username'])

        # Diff
        changes = []
        cwd = context.database.path
        password_re = compile('<password>(.*)</password>')
        for line in git.get_diff(revision, cwd):
            css = None
            if line.startswith('index') or \
               line.startswith('---') or \
               line.startswith('+++') or \
               line.startswith('@@'):
                continue
            elif line.startswith('-'):
                css = 'rem'
            elif line.startswith('+'):
                css = 'add'
            elif line.startswith('diff'):
                css = 'header'
            # HACK for security, we hide password
            line = sub(password_re, '<password>***</password>', line)
            # Add the line
            changes.append({'css': css, 'value': line})
        ns['changes'] = changes
        return ns
