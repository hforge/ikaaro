# -*- coding: UTF-8 -*-
# Copyright (C) 2011 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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

# Import from itools
from itools.database import AndQuery, OrQuery, PhraseQuery
from itools.gettext import MSG
from itools.web import get_context

# Import from ikaaro
from autoadd import AutoAdd
from config import Configuration
from resource_ import DBResource
from folder import Folder
from folder_views import Folder_NewResource, Folder_BrowseContent
from registry import get_resource_class
from utils import get_base_path_query


class SavedSearch_New(AutoAdd):

    fields = ['title']

    def get_container(self, resource, context, form):
        return resource


class SavedSearch_Results(Folder_BrowseContent):

    title = MSG(u'View results')
    search_template = None

    def get_items_query(self, resource, context):
        return resource.get_search_query()


class SavedSearch(DBResource):
    """Base class."""

    class_id = 'saved-search'
    class_title = MSG(u'Saved Search')
    class_description = MSG(u'...')
    class_icon48 = 'icons/48x48/search.png'

    # Views
    class_views = ['edit', 'results']
    new_instance = SavedSearch_New()
    results = SavedSearch_Results()


    def get_search_query(self):
        query = AndQuery()

        # Search in website
        site_root = self.get_site_root()
        query.append(get_base_path_query(site_root.abspath,
                                         include_container=True))

        # Search values
        for name in self.fields:
            if not name.startswith('search_'):
                continue
            value = self.get_value(name)
            if not value:
                continue
            field = self.get_field(name)
            name = name[7:]
            if field.multiple:
                subquery = [ PhraseQuery(name, x) for x in value ]
                if len(subquery) == 1:
                    subquery = subquery[0]
                else:
                    subquery = OrQuery(*subquery)
            else:
                subquery = PhraseQuery(name, value)
            query.append(subquery)

        return query


    def match_resource(self, resource):
        query = self.get_search_query()
        query.append(PhraseQuery('abspath', str(resource.abspath)))
        results = get_context().root.search(query)
        return len(results)



class Config_Searches_New(Folder_NewResource):

    def get_items(self, resource, context):
        return resource.get_document_types()



class Config_Searches(Folder):

    class_id = 'config-searches'
    class_title = MSG(u'Saved Searches')
    class_description = MSG(u'...')
    class_icon48 = 'icons/48x48/search.png'

    # Configuration
    config_name = 'searches'
    config_group = 'access'

    # Views
    class_views = ['browse_content', 'new_search', 'edit', 'commit_log']
    new_search = Config_Searches_New()


    def get_document_types(self):
        return [
            get_resource_class(x) for x in self._register_document_types ]



Configuration.register_plugin(Config_Searches)
