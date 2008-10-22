# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Luis Arturo Belmar-Letelier <luis@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2007-2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007-2008 Nicolas Deram <nicolas@itaapy.com>
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
from datetime import datetime, timedelta
from operator import itemgetter
from string import Template

# Import from itools
from itools.datatypes import Integer, String, Unicode
from itools.gettext import MSG
from itools.uri import Reference
from itools.web import ERROR
from itools.xapian import EqQuery, RangeQuery, AndQuery, OrQuery, PhraseQuery

# Import from ikaaro
from ikaaro.folder import Folder
from ikaaro.registry import register_resource_class
from resources import Resources
from stored import StoredSearch, StoredSearchFile
from tables import Tracker_TableResource, Tracker_TableHandler
from tables import ModulesResource, ModulesHandler
from tables import VersionsResource, VersionsHandler
from tracker_views import GoToIssueMenu, StoredSearchesMenu
from tracker_views import TrackerSearch, TrackerView, TrackerAddIssue
from tracker_views import TrackerGoToIssue
from tracker_views import TrackerRememberSearch, TrackerForgetSearch
from tracker_views import TrackerExportToText, TrackerChangeSeveralBugs
from tracker_views import TrackerExportToCSVForm, TrackerExportToCSV


resolution = timedelta.resolution



default_types = [
    u'Bug', u'New Feature', u'Security Issue', u'Stability Issue',
    u'Data Corruption Issue', u'Performance Improvement',
    u'Technology Upgrade']

default_tables = [
    ('products', []),
    ('types', default_types),
    ('states', [u'Open', u'Fixed', u'Verified', u'Closed']),
    ('priorities', [u'High', u'Medium', u'Low']),
    ]


class Tracker(Folder):

    class_id = 'tracker'
    class_version = '20081015'
    class_title = MSG(u'Issue Tracker')
    class_description = MSG(u'To manage bugs and tasks')
    class_icon16 = 'tracker/tracker16.png'
    class_icon48 = 'tracker/tracker48.png'
    class_views = ['search', 'add_issue', 'browse_content', 'edit']

    __fixed_handlers__ = ['products', 'modules', 'versions', 'types',
        'priorities', 'states', 'resources']

    @staticmethod
    def _make_resource(cls, folder, name):
        Folder._make_resource(cls, folder, name)
        # Products / Types / Priorities / States
        for table_name, values in default_tables:
            table_path = '%s/%s' % (name, table_name)
            table = Tracker_TableHandler()
            for title in values:
                table.add_record({'title': title})
            folder.set_handler(table_path, table)
            metadata = Tracker_TableResource.build_metadata()
            folder.set_handler('%s.metadata' % table_path, metadata)
        # Modules
        table = ModulesHandler()
        folder.set_handler('%s/modules' % name, table)
        metadata = ModulesResource.build_metadata()
        folder.set_handler('%s/modules.metadata' % name, metadata)
        # Versions
        table = VersionsHandler()
        folder.set_handler('%s/versions' % name, table)
        metadata = VersionsResource.build_metadata()
        folder.set_handler('%s/versions.metadata' % name, metadata)
        # Pre-defined stored searches
        open = StoredSearchFile(state='0')
        not_assigned = StoredSearchFile(assigned_to='nobody')
        high_priority = StoredSearchFile(state='0', priority='0')
        i = 0
        for search, title in [(open, u'Open Issues'),
                              (not_assigned, u'Not Assigned'),
                              (high_priority, u'High Priority')]:
            folder.set_handler('%s/s%s' % (name, i), search)
            metadata = StoredSearch.build_metadata(title={'en': title})
            folder.set_handler('%s/s%s.metadata' % (name, i), metadata)
            i += 1
        metadata = Resources.build_metadata()
        folder.set_handler('%s/resources.metadata' % name, metadata)


    def get_document_types(self):
        return []


    #######################################################################
    # API
    #######################################################################
    def get_new_id(self, prefix=''):
        ids = []
        for name in self.get_names():
            if prefix:
                if not name.startswith(prefix):
                    continue
                name = name[len(prefix):]
            try:
                id = int(name)
            except ValueError:
                continue
            ids.append(id)

        if ids:
            ids.sort()
            return prefix + str(ids[-1] + 1)

        return prefix + '0'


    def get_members_namespace(self, value, not_assigned=False):
        """Returns a namespace (list of dictionaries) to be used for the
        selection box of users (the 'assigned to' and 'cc' fields).
        """
        users = self.get_resource('/users')
        members = []
        if not_assigned is True:
            members.append({'id': 'nobody', 'title': 'NOT ASSIGNED'})
        for username in self.get_site_root().get_members():
            user = users.get_resource(username)
            members.append({'id': username, 'title': user.get_title()})
        # Select
        if isinstance(value, str):
            value = [value]
        for member in members:
            member['is_selected'] = (member['id'] in value)
        members.sort(key=itemgetter('title'))

        return members


    def get_search_results(self, context):
        """Method that return a list of issues that correspond to the search
        """
        users = self.get_resource('/users')
        # Choose stored Search or personalized search
        query = context.query
        search_name = query.get('search_name')
        if search_name:
            try:
                search = self.get_resource(search_name)
            except LookupError:
                msg = ERROR(u'Unknown stored search "${sname}".')
                goto = ';search'
                return context.come_back(msg, goto=goto, sname=search_name)
            get_value = search.handler.get_value
            get_values = search.get_values
        else:
            get_value = context.get_form_value
            get_values = context.get_form_values
        # Get search criteria
        text = get_value('text', type=Unicode)
        if text is not None:
            text = text.strip().lower()
        mtime = get_value('mtime', type=Integer)
        products = get_values('product', type=Integer)
        modules = get_values('module', type=Integer)
        versions = get_values('version', type=Integer)
        types = get_values('type', type=Integer)
        priorities = get_values('priority', type=Integer)
        assigns = get_values('assigned_to', type=String)
        states = get_values('state', type=Integer)

        # Build the query
        abspath = self.get_canonical_path()
        query = [
            EqQuery('parent_path', str(abspath)),
            EqQuery('format', 'issue')]
        # Text search
        if text:
            query2 = [PhraseQuery('title', text), PhraseQuery('text', text)]
            query2 = OrQuery(*query2)
            query.append(query2)
        # Metadata
        for name, data in (('product', products), ('module', modules),
                           ('version', versions), ('type', types),
                           ('priority', priorities), ('state', states)):
            if len(data) > 0:
                query2 = [ EqQuery(name, value) for value in data ]
                query2 = OrQuery(*query2)
                query.append(query2)
        # Modification time
        if mtime:
            date = datetime.now() - timedelta(mtime)
            date = date.strftime('%Y%m%d%H%M%S')
            query2 = RangeQuery('mtime', date, None)
            query.append(query2)
        # Assign To
        if len(assigns) > 0:
            query2 = []
            for value in assigns:
                value = value or 'nobody'
                query2.append(EqQuery('assigned_to', value))
            query2 = OrQuery(*query2)
            query.append(query2)

        # Execute the search
        query = AndQuery(*query)
        return context.root.search(query)


    #######################################################################
    # User Interface
    #######################################################################
    context_menus = [GoToIssueMenu(), StoredSearchesMenu()]

    # Views
    search = TrackerSearch()
    view = TrackerView()
    add_issue = TrackerAddIssue()
    remember_search = TrackerRememberSearch()
    forget_search = TrackerForgetSearch()
    go_to_issue = TrackerGoToIssue()
    export_to_text = TrackerExportToText()
    export_to_csv_form = TrackerExportToCSVForm()
    export_to_csv = TrackerExportToCSV()
    change_several_bugs = TrackerChangeSeveralBugs()


    #######################################################################
    # Update
    #######################################################################
    def update_20080407(self):
        """Add resources to tracker.
        """
        metadata = Resources.build_metadata()
        self.handler.set_handler('resources.metadata', metadata)


    def update_20081015(self):
        """Add the 'products' table.
        """
        # Add the products table
        cls = Tracker_TableResource
        cls.make_resource(cls, self, 'products')
        # Change the format of the 'modules' table
        resource = self.get_resource('modules')
        metadata = resource.metadata
        metadata.set_changed()
        metadata.format = ModulesResource.class_id



###########################################################################
# Register
###########################################################################
register_resource_class(Tracker)
