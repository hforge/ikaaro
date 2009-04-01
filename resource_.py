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

# Import from itools
from itools.datatypes import Unicode
from itools.gettext import MSG
from itools.web import Resource, get_context
from itools.xapian import CatalogAware
from itools.xapian import TextField, KeywordField, IntegerField, BoolField
from itools.xapian import PhraseQuery

# Import from ikaaro
from lock import Lock
from metadata import Metadata
from resource_views import DBResource_NewInstance, DBResource_Edit
from resource_views import DBResource_AddImage, DBResource_AddLink
from resource_views import LoginView, LogoutView
from workflow import WorkflowAware



class IResource(Resource):

    class_views = []
    context_menus = []


    def get_site_root(self):
        from website import WebSite
        resource = self
        while not isinstance(resource, WebSite):
            resource = resource.parent
        return resource


    def get_default_view_name(self):
        views = self.class_views
        if not views:
            return None
        context = get_context()
        user = context.user
        ac = self.get_access_control()
        for view_name in views:
            view = getattr(self, view_name, None)
            if ac.is_access_allowed(user, self, view):
                return view_name
        return views[0]


    def get_context_menus(self):
        return self.context_menus


    ########################################################################
    # Properties
    ########################################################################
    def get_property_and_language(self, name, language=None):
        return None, None


    def get_property(self, name, language=None):
        return self.get_property_and_language(name, language=language)[0]


    def get_title(self):
        return self.name


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
        user = get_context().user
        ac = self.get_access_control()
        for name in self.class_views:
            view_name = name.split('?')[0]
            view = self.get_view(view_name)
            if ac.is_access_allowed(user, self, view):
                yield name, view



class DBResource(CatalogAware, IResource):

    def __init__(self, metadata):
        self.metadata = metadata
        self._handler = None
        # The tree
        self.name = ''
        self.parent = None


    @staticmethod
    def make_resource(cls, container, name, *args, **kw):
        cls._make_resource(cls, container.handler, name, *args, **kw)
        resource = container.get_resource(name)
        # Events, add
        get_context().server.add_resource(resource)

        return resource


    @staticmethod
    def _make_resource(cls, folder, name, **kw):
        metadata = cls.build_metadata(**kw)
        folder.set_handler('%s.metadata' % name, metadata)


    @classmethod
    def build_metadata(cls, format=None, **kw):
        """Return a Metadata object with sensible default values.
        """
        if format is None:
            format = cls.class_id

        if issubclass(cls, WorkflowAware):
            schema = cls.get_metadata_schema()
            state = schema['state'].get_default()
            if state is None:
                state  = cls.workflow.initstate
            kw['state'] = state

        return Metadata(handler_class=cls, format=format, **kw)


    def get_handler(self):
        if self._handler is None:
            cls = self.class_handler
            database = self.metadata.database
            if self.parent is None:
                uri = self.metadata.uri.resolve('.')
            else:
                uri = self.metadata.uri.resolve(self.name)
            if database.has_handler(uri):
                self._handler = database.get_handler(uri, cls=cls)
            else:
                handler = cls()
                handler.database = database
                handler.uri = uri
                handler.timestamp = None
                handler.dirty = datetime.now()
                database.add_to_cache(uri, handler)
                self._handler = handler
        return self._handler

    handler = property(get_handler, None, None, '')


    def load_handlers(self):
        self.get_handlers()


    ########################################################################
    # Metadata
    ########################################################################
    @classmethod
    def get_metadata_schema(cls):
        return {
            'title': Unicode,
            'description': Unicode,
            'subject': Unicode,
            }


    def has_property(self, name, language=None):
        return self.metadata.has_property(name, language=language)


    def get_property_and_language(self, name, language=None):
        return self.metadata.get_property_and_language(name,
                                                       language=language)


    def set_property(self, name, value, language=None):
        get_context().server.change_resource(self)
        self.metadata.set_property(name, value, language=language)


    def del_property(self, name, language=None):
        get_context().server.change_resource(self)
        self.metadata.del_property(name, language=language)


    ########################################################################
    # Indexing
    ########################################################################
    def to_text(self):
        raise NotImplementedError


    def get_catalog_fields(self):
        return [
            KeywordField('abspath', is_stored=True),
            TextField('text'),
            TextField('title', is_stored=True),
            BoolField('is_role_aware'),
            BoolField('is_image'),
            KeywordField('format', is_stored=True),
            KeywordField('workflow_state', is_stored=True),
            KeywordField('members'),
            # For referencial-integrity, keep links between cms resources,
            # where a link is the physical path.
            KeywordField('links'),
            # Folder's view
            KeywordField('parent_path'),
            KeywordField('name', is_stored=True),
            KeywordField('mtime', is_indexed=True, is_stored=True),
            IntegerField('size', is_indexed=False, is_stored=True)]


    def get_catalog_values(self):
        from access import RoleAware
        from file import File, Image

        abspath = self.get_canonical_path()
        mtime = self.get_mtime()
        if mtime is None:
            mtime = datetime.now()

        # FIXME Index a single language for now
        site_root = self.get_site_root()
        languages = site_root.get_property('website_languages')
        language = languages[0]

        document = {
            'name': self.name,
            'abspath': str(abspath),
            'format': self.metadata.format,
            'title': self.get_title(language=language),
            'mtime': mtime.strftime('%Y%m%d%H%M%S')}

        # Full text
        context = get_context()
        if context is not None and context.server.index_text:
            try:
                text = self.to_text()
            except NotImplementedError:
                pass
            except:
                server = context.server
                server.log_error(context)
                log = "%s failed" % self.get_abspath()
                server.event_log.write(log)
                server.event_log.flush()
            else:
                document['text'] = text

        # Links
        document['links'] = self.get_links()

        # Parent path
        if str(abspath) != '/':
            parent_path = abspath.resolve2('..')
            document['parent_path'] = str(parent_path)

        # Size
        if isinstance(self, File):
            # FIXME We add an arbitrary size so files will always be bigger
            # than folders. This won't work when there is a folder with more
            # than that size.
            document['size'] = 2**30 + self.get_size()
        else:
            names = self.get_names()
            document['size'] = len(names)

        # Workflow state
        if isinstance(self, WorkflowAware):
            document['workflow_state'] = self.get_workflow_state()

        # Role Aware
        if isinstance(self, RoleAware):
            document['is_role_aware'] = True
            document['members'] = self.get_members()

        # Browse in image mode
        document['is_image'] = isinstance(self, Image)

        return document


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


    def update_links(self, new_name, base_path):
        """The resource must update its links to itself.
        """
        # Check referencial-integrity
        catalog = get_context().server.catalog
        # The catalog is not available when updating (icms-update.py)
        # FIXME We do not guarantee referencial-integrity when updating
        if catalog is None:
            return

        old_path = self.get_abspath()
        new_path = base_path.resolve2(new_name)

        # Get all the resources that have a link to me
        query = PhraseQuery('links', str(old_path))
        results = catalog.search(query).get_documents()
        for result in results:
            resource = self.get_resource(result.abspath)
            resource.change_link(old_path, new_path)


    def change_link(self, old_path, new_path):
        """The resource "old_name" has a "new_name", we must update its link
        """
        pass


    def get_mtime(self):
        handlers = [self.metadata] + self.get_handlers()

        mtimes = []
        for handler in handlers:
            if handler is not None:
                mtime = handler.get_mtime()
                if mtime is not None:
                    mtimes.append(mtime)

        if not mtimes:
            return None
        return max(mtimes)


    def get_links(self):
        return []


    ########################################################################
    # Upgrade
    ########################################################################
    def get_next_versions(self):
        cls_version = self.class_version
        obj_version = self.metadata.version
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
        metadata.version = version


    ########################################################################
    # Lock/Unlock/Put
    ########################################################################
    def lock(self):
        lock = Lock(username=get_context().user.name)

        self = self.get_real_resource()
        if self.parent is None:
            self.handler.set_handler('.lock', lock)
        else:
            self.parent.handler.set_handler('%s.lock' % self.name, lock)

        return lock.key


    def unlock(self):
        self = self.get_real_resource()
        if self.parent is None:
            self.handler.del_handler('.lock')
        else:
            self.parent.handler.del_handler('%s.lock' % self.name)


    def is_locked(self):
        self = self.get_real_resource()
        if self.parent is None:
            return self.handler.has_handler('.lock')
        return self.parent.handler.has_handler('%s.lock' % self.name)


    def get_lock(self):
        self = self.get_real_resource()
        if self.parent is None:
            return self.handler.get_handler('.lock')
        return self.parent.handler.get_handler('%s.lock' % self.name)


    def put(self, context):
        # Save the data
        body = context.get_form_value('body')
        self.handler.load_state_from_string(body)
        context.server.change_resource(self)


    ########################################################################
    # User interface
    ########################################################################
    def get_title(self, language=None):
        title = self.get_property('title', language=language)
        if title:
            return title
        # Fallback to the resource's name
        title = self.name
        if isinstance(title, MSG):
            return title.gettext(language)
        return title


    def get_content_language(self, context, languages=None):
        if languages is None:
            site_root = self.get_site_root()
            languages = site_root.get_property('website_languages')

        # The 'content_language' query parameter has preference
        language = context.get_query_value('content_language')
        if language in languages:
            return language

        # Language negotiation
        return context.accept_language.select_language(languages)


    # Views
    new_instance = DBResource_NewInstance()
    login = LoginView()
    logout = LogoutView()
    edit = DBResource_Edit()
    add_image = DBResource_AddImage()
    add_link = DBResource_AddLink()

