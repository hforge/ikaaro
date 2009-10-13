# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2007-2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2008 Matthieu France <matthieu@itaapy.com>
# Copyright (C) 2008 Nicolas Deram <nicolas@itaapy.com>
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
from random import random
from time import time

# Import from itools
from itools.core import freeze, lazy
from itools.csv import Property
from itools.datatypes import Unicode, String, Integer, Boolean, DateTime
from itools.http import get_context
from itools.log import log_warning
from itools.uri import Path
from itools.web import Resource
from itools.xapian import CatalogAware, PhraseQuery

# Import from ikaaro
from metadata import Metadata
from registry import register_field, register_resource_class
from resource_views import DBResource_Edit, DBResource_Backlinks
from resource_views import DBResource_AddImage, DBResource_AddLink
from resource_views import DBResource_AddMedia, LoginView, LogoutView
from revisions_views import DBResource_LastChanges, DBResource_Changes
from workflow import WorkflowAware
from views_new import NewInstance


class IResource(Resource):

    class_views = []
    context_menus = []


    def get_parent(self):
        # Special case: the root
        if not self.path:
            return None
        path = self.path[:-1]
        return self.context.get_resource(path)


    def get_name(self):
        # Special case: the root
        if not self.path:
            return None

        return self.path[-1]


    def get_site_root(self):
        from website import WebSite
        resource = self
        while not isinstance(resource, WebSite):
            resource = resource.get_parent()
        return resource


    def get_default_view_name(self):
        views = self.class_views
        if not views:
            return None
        context = get_context()
        ac = self.get_access_control()
        for view_name in views:
            view = getattr(self, view_name, None)
            if ac.is_access_allowed(context, self, view):
                return view_name
        return views[0]


    def get_context_menus(self):
        return self.context_menus


    ########################################################################
    # Properties
    ########################################################################
    def get_title(self):
        return unicode(self.name)


    def get_page_title(self):
        return self.get_title()


    ########################################################################
    # Icons
    ########################################################################
    @classmethod
    def get_class_icon(cls, size=16):
        icon = getattr(cls, 'class_icon%s' % size, None)
        if icon is None:
            return None
        return '/ui/%s' % icon


    @classmethod
    def get_resource_icon(cls, size=16):
        icon = getattr(cls, 'icon%s' % size, None)
        if icon is None:
            return cls.get_class_icon(size)
        return ';icon%s' % size


    def get_method_icon(self, view, size='16x16', **kw):
        icon = getattr(view, 'icon', None)
        if icon is None:
            return None
        if callable(icon):
            icon = icon(self, **kw)
        return '/ui/icons/%s/%s' % (size, icon)


    ########################################################################
    # User interface
    ########################################################################
    def get_views(self):
        context = get_context()
        ac = self.get_access_control()
        for name in self.class_views:
            view_name = name.split('?')[0]
            view = self.get_view(view_name)
            if ac.is_access_allowed(context, self, view):
                yield name, view



###########################################################################
# Database resources
###########################################################################
class DBResourceMetaclass(type):

    def __new__(mcs, name, bases, dict):
        cls = type.__new__(mcs, name, bases, dict)
        if 'class_id' in dict:
            register_resource_class(cls)
        for name, dt in cls.class_schema.iteritems():
            if getattr(dt, 'indexed', False) or getattr(dt, 'stored', False):
                register_field(name, dt)
        return cls



class DBResource(CatalogAware, IResource):

    __metaclass__ = DBResourceMetaclass

    def __init__(self, metadata=None, brain=None):
        self._handler = None

        # Case 1. The brain
        if brain:
            if metadata:
                raise ValueError, 'expected brain or metadata, not both'
            self.brain = brain
        # Case 2. The metadata
        else:
            if not metadata:
                raise ValueError, 'expected brain or metadata, got none'
            self.brain = None
            self.metadata = metadata


    @lazy
    def metadata(self):
        path = self.path
        return self.context._get_metadata(str(path), path)


    def init_resource(self, **kw):
        """Return a Metadata object with sensible default values.
        """
        metadata = self.metadata
        # Properties
        for key in kw:
            value = kw[key]
            if type(value) is dict:
                for lang in value:
                    property = Property(value[lang], lang=lang)
                    metadata._set_property(key, property)
            else:
                metadata._set_property(key, value)

        # Workflow State (default)
        if kw.get('state') is None and isinstance(self, WorkflowAware):
            datatype = self.get_property_datatype('state')
            state = datatype.get_default()
            if state is None:
                state  = self.workflow.initstate
            metadata._set_property('state', state)


    def get_handler(self):
        if self._handler is None:
            cls = self.class_handler
            database = self.metadata.database
            uri = self.metadata.uri[:-len('.metadata')]
            if database.has_handler(uri):
                handler = database.get_handler(uri, cls=cls)
            else:
                handler = cls()
                database.push_handler(uri, handler)
            self._handler = handler
        return self._handler

    handler = property(get_handler)


    def load_handlers(self):
        self.get_handlers()


    ########################################################################
    # Metadata
    ########################################################################
    Multilingual = Unicode(multilingual=True)
    class_schema = freeze({
        # Metadata
        'version': String(source='metadata'),
        'title': Multilingual(source='metadata', indexed=True, stored=True),
        'description': Multilingual(source='metadata', indexed=True),
        'subject': Multilingual(source='metadata', indexed=True),
        'lock': String,
        # Key & class id
        'abspath': String(key_field=True, indexed=True, stored=True),
        'format': String(indexed=True, stored=True),
        # Versioning
        'mtime': DateTime(indexed=True, stored=True),
        'last_author': String(indexed=False, stored=True),
        # Folder's view
        'parent_path': String(indexed=True),
        'name': String(stored=True, indexed=True),
        'size': Integer(stored=True, indexed=False),
        # Referential integrity
        'links': String(multiple=True, indexed=True),
        # Full text search
        'text': Unicode(indexed=True),
        # Various classifications
        'is_role_aware': Boolean(indexed=True),
        'is_folder': Boolean(indexed=True),
        'is_image': Boolean(indexed=True),
        })


    @classmethod
    def get_property_datatype(cls, name, default=None):
        datatype = cls.class_schema.get(name)
        if datatype and getattr(datatype, 'source', None) == 'metadata':
            return datatype
        return default


    def has_property(self, name, language=None):
        return self.metadata.has_property(name, language=language)


    def get_property(self, name, language=None):
        return self.metadata.get_property(name, language=language)


    def set_property(self, name, value, language=None):
        get_context().change_resource(self)
        if language:
            value = Property(value, lang=language)
        self.metadata.set_property(name, value)


    def del_property(self, name):
        get_context().change_resource(self)
        self.metadata.del_property(name)


    ########################################################################
    # Versioning
    ########################################################################
    def get_files_to_archive(self, content=False):
        raise NotImplementedError


    def get_revisions(self, n=None, content=False):
        files = self.get_files_to_archive(content)
        database = get_context().database
        return database.get_revisions(files, n)


    def get_last_revision(self):
        files = self.get_files_to_archive()
        database = get_context().database
        return database.get_last_revision(files)


    def get_owner(self):
        revisions = self.get_revisions()
        if not revisions:
            return None
        return revisions[-1]['username']


    ########################################################################
    # Values
    ########################################################################
    def get_value(self, name, language=None):
        datatype = self.class_schema.get(name)
        if not datatype:
            err = "field '%s' not defined by '%s' schema"
            raise ValueError, err % (name, self.__class__.__name__)

        # Case 1: Get it from the brain
        if getattr(datatype, 'stored', False) and self.brain:
            if language:
                name = '%s_%s' % (name, language)
            return getattr(self.brain, name)

        # Case 2: Explicit getter method is required
        getter = getattr(self, 'get_%s' % name, None)
        if getter:
            if language:
                return getter(language=language)
            return getter()

        # Case 3: Metadata
        if getattr(datatype, 'source', None) == 'metadata':
            return self.metadata.get_value(name, language=language)

        # Error
        err = "unable to get '%s' field from '%s'"
        raise ValueError, err % (name, self.__class__.__name__)


    def get_abspath(self):
        path = self.get_physical_path()
        return str(path)


    def get_format(self):
        return self.metadata.format


    def get_title(self, language=None):
        title = self.metadata.get_property('title', language=language)
        if title:
            return title.value
        # Fallback to the resource's name
        return unicode(self.get_name())


    def get_text(self):
        """This function must return:
           1) An unicode text.
            or
           2) A dict in a multilingual context:
              {'fr': u'....',
               'en': u'....' ....}
        """
        return None


    ########################################################################
    # Indexing
    ########################################################################
    def get_catalog_values(self):
        # Local variables
        site_root = self.get_site_root()
        languages = site_root.metadata.get_value('website_languages')
        get_property = self.metadata.get_property

        server = getattr(self.context, 'server', None)
        index_text = server.index_text if server else False

        # Build dictionary
        values = {}
        for name, datatype in self.class_schema.iteritems():
            indexed = getattr(datatype, 'indexed', False)
            stored = getattr(datatype, 'stored', False)
            if not indexed and not stored:
                continue

            # Special case: text
            if name == 'text' and not index_text:
                continue

            # Case 1: Monolingual
            if not getattr(datatype, 'multilingual', False):
                try:
                    value = self.get_value(name)
                except Exception:
                    msg = 'Error indexing "%s" field' % name
                    log_warning(msg, domain='ikaaro')
                    continue
                if value is not None:
                    values[name] = value
                continue

            # Case 2: Multilingual
            values[name] = {}
            for language in languages:
                try:
                    value = self.get_value(name, language=language)
                except Exception:
                    msg = 'Error indexing "%s" field' % name
                    log_warning(msg, domain='ikaaro')
                    continue
                if value is not None:
                    values[name][language] = value

        # Ok
        return values


    def get_links(self):
        return []


    def get_parent_path(self):
        abspath = self.get_physical_path()
        if not abspath:
            return None
        return str(abspath[:-1])


    def get_is_folder(self):
        return False


    def get_is_image(self):
        return False


    def get_is_role_aware(self):
        return False


    def get_last_author(self):
        revision = self.get_last_revision()
        return revision['username'] if revision else None


    def get_mtime(self):
        revision = self.get_last_revision()
        return revision['date'] if revision else None


    ########################################################################
    # API
    ########################################################################
    def get_handlers(self):
        """Return all the handlers attached to this resource, except the
        metadata.
        """
        return [self.handler]


    def rename_handlers(self, new_name):
        """Consider we want to rename this resource to the given 'new_name',
        return the old a new names for all the attached handlers (except the
        metadata).

        This method is required by the "move_resource" method.
        """
        return [(self.name, new_name)]


    def _on_move_resource(self, source):
        """This method is to be called when moving the resource somewhere
        else, before it has been moved.  The 'target' parameter is the
        place it will be moved to.

        Called by 'Folder.move_resource'.  It is used to update the resources
        that link to this one.
        """
        # (1) Update links to other resources
        target = self.get_canonical_path()
        self.update_relative_links(target)

        # (2) Update resources that link to me
        # Check referencial-integrity
        database = get_context().database

        # Get all the resources that have a link to me
        query = PhraseQuery('links', str(source))
        results = database.catalog.search(query).get_documents()
        for resource in results:
            path = resource.abspath
            path = database.resources_old2new.get(path, path)
            resource = self.get_resource(path)
            resource.update_links(source, target)


    def update_links(self, source, target):
        """The resource identified by 'source' is going to be moved to
        'target'.  Update our links to it.

        The parameters 'source' and 'target' are absolute 'Path' objects.
        """


    def update_relative_links(self, target):
        """Update the relative links coming out from this resource, so they
        are not broken when this resource moves to 'target'.
        """


    ########################################################################
    # Upgrade
    ########################################################################
    def get_next_versions(self):
        cls_version = self.class_version
        obj_version = self.metadata.get_property('version').value
        # Set zero version if the resource does not have a version
        if obj_version is None:
            obj_version = '00000000'

        # Get all the version numbers
        versions = []
        for cls in self.__class__.mro():
            for name in cls.__dict__.keys():
                if not name.startswith('update_'):
                    continue
                kk, version = name.split('_', 1)
                if len(version) != 8:
                    continue
                try:
                    int(version)
                except ValueError:
                    continue
                if version > obj_version and version <= cls_version:
                    versions.append(version)

        versions.sort()
        return versions


    def update(self, version):
        # We don't check the version is good
        getattr(self, 'update_%s' % version)()
        metadata = self.metadata
        metadata.set_changed()
        metadata.set_property('version', version)


    ########################################################################
    # Lock/Unlock/Put
    ########################################################################
    def lock(self):
        # key
        key = '%s-%s-00105A989226:%.03f' % (random(), random(), time())
        # lock
        username = get_context().user.get_name()
        timestamp = datetime.now()
        timestamp = DateTime.encode(timestamp)
        lock = '%s#%s#%s' % (username, timestamp, key)
        self.set_property('lock', lock)
        # Ok
        return key


    def unlock(self):
        self.del_property('lock')


    def is_locked(self):
        return self.has_property('lock')


    def get_lock(self):
        lock = self.get_value('lock')
        username, timestamp, key = lock.split('#')
        timestamp = timestamp.split('.')[0]
        timestamp = DateTime.decode(timestamp)
        return username, timestamp, key


    ########################################################################
    # User interface
    ########################################################################
    def get_content_language(self, context, languages=None):
        if languages is None:
            site_root = self.get_site_root()
            languages = site_root.get_value('website_languages')

        # The 'content_language' query parameter has preference
        language = context.get_query_value('content_language')
        if language in languages:
            return language

        # Language negotiation
        return context.accept_language.select_language(languages)


    ########################################################################
    # Cut & Paste Resources
    ########################################################################
    def can_paste(self, source):
        """Is the source resource can be pasted into myself.
        Question is "can I handle this type of resource?"
        """
        raise NotImplementedError


    def can_paste_into(self, target):
        """Can I be pasted into the given target.
        Question is "Is this container compatible with myself?"
        """
        # No restriction by default. Functional modules will want to keep
        # their specific resources for them.
        return True


    # Views
    new_instance = NewInstance()
    login = LoginView()
    logout = LogoutView()
    edit = DBResource_Edit()
    add_image = DBResource_AddImage()
    add_link = DBResource_AddLink()
    add_media = DBResource_AddMedia()
    last_changes = DBResource_LastChanges()
    changes = DBResource_Changes()
    backlinks = DBResource_Backlinks()

