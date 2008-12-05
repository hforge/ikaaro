# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2008 Henry Obein <henry@itaapy.com>
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
from operator import itemgetter

# Import from itools
from itools.datatypes import DateTime, String
from itools.gettext import MSG
from itools.i18n import format_datetime
from itools.web import get_context, STLView
from itools.xapian import KeywordField, BoolField

# Import from ikaaro
from metadata import Record
from resource_ import DBResource


###########################################################################
# Views
###########################################################################
class HistoryView(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'History')
    icon = 'history.png'
    template = '/ui/file/history.xml'


    def get_namespace(self, resource, context):
        return {
            'revisions': resource.get_revisions(context),
        }



###########################################################################
# Model
###########################################################################
class History(Record):

    schema = {
        'date': DateTime,
        'user': String,
        'size': String}


class VersioningAware(DBResource):

    @classmethod
    def get_metadata_schema(cls):
        schema = DBResource.get_metadata_schema()
        schema['history'] = History
        return schema


    ########################################################################
    # API
    ########################################################################
    def commit_revision(self):
        context = get_context()
        username = ''
        if context is not None:
            user = context.user
            if user is not None:
                username = user.name

        property = {'user': username,
                    'date': datetime.now(),
                    'size': str(self.get_size())}
        self.metadata.set_property('history', property)


    def get_revisions(self, context):
        accept = context.accept_language
        revisions = []

        for revision in self.get_property('history'):
            date = revision['date']
            revisions.append({
                'username': revision['user'],
                'date': format_datetime(date, accept=accept),
                'sort_date': date,
                'size': revision['size']})

        revisions.sort(key=itemgetter('sort_date'), reverse=True)
        return revisions


    def get_owner(self):
        history = self.get_property('history')
        if not history:
            return None
        return history[0]['user']


    def get_last_author(self):
        history = self.get_property('history')
        if history:
            return history[-1]['user']


    def get_mtime(self):
        history = self.get_property('history')
        if not history:
            return DBResource.get_mtime(self)
        return history[-1]['date']


    ########################################################################
    # Index & Search
    ########################################################################
    def get_catalog_fields(self):
        return DBResource.get_catalog_fields(self) + [
            # Versioning Aware
            BoolField('is_version_aware'),
            KeywordField('last_author', is_indexed=False, is_stored=True)]


    def get_catalog_values(self):
        document = DBResource.get_catalog_values(self)

        document['is_version_aware'] = True
        # Last Author (used in the Last Changes view)
        last_author = self.get_last_author()
        if last_author is not None:
            users = self.get_resource('/users')
            try:
                user = users.get_resource(last_author)
            except LookupError:
                document['last_author'] = None
            else:
                document['last_author'] = user.get_title()

        return document


    ########################################################################
    # User Interface
    ########################################################################
    history = HistoryView()
