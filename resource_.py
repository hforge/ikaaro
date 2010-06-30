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

# Import from itools
from itools.core import freeze
from itools.csv import Property
from itools.database import register_field
from itools.datatypes import Unicode, String, Boolean, DateTime
from itools.log import log_error
from itools.uri import Path
from itools.web import Resource, get_context
from itools.xapian import CatalogAware, PhraseQuery

# Import from ikaaro
from popup import DBResource_AddImage, DBResource_AddLink
from popup import DBResource_AddMedia
from registry import register_resource_class
from resource_views import DBResource_Edit, DBResource_Backlinks
from resource_views import LoginView, LogoutView
from resource_views import Put_View, Delete_View
from revisions_views import DBResource_CommitLog, DBResource_Changes
from workflow import WorkflowAware
from views_new import NewInstance


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
    @classmethod
    def get_property_datatype(cls, name, default=String):
        return default


    def _get_property(self, name, language=None):
        return None


    def get_property(self, name, language=None):
        """Return the property value for the given property name.
        """
        property = self._get_property(name, language=language)
        # Default
        if not property:
            datatype = self.get_property_datatype(name)
            return datatype.get_default()

        # Multiple
        if type(property) is list:
            return [ x.value for x in property ]

        # Simple
        return property.value


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
        user = get_context().user
        ac = self.get_access_control()
        for name in self.class_views:
            view_name = name.split('?')[0]
            view = self.get_view(view_name)
            if ac.is_access_allowed(user, self, view):
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

    def __init__(self, metadata):
        self.metadata = metadata
        self._handler = None
        # The tree
        self.name = ''
        self.parent = None


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
            fs = database.fs
            if self.parent is None:
                key = fs.resolve(self.metadata.key, '.')
            else:
                key = fs.resolve(self.metadata.key, self.name)
            if database.has_handler(key):
                handler = database.get_handler(key, cls=cls)
            else:
                handler = cls()
                database.push_phantom(key, handler)
            self._handler = handler
        return self._handler

    handler = property(get_handler)


    def load_handlers(self):
        self.get_handlers()


    def traverse_resources(self):
        yield self


    ########################################################################
    # Metadata
    ########################################################################
    Multilingual = Unicode(multilingual=True)
    class_schema = freeze({
        # Metadata
        'version': String(source='metadata'),
        'mtime': DateTime(source='metadata', indexed=True, stored=True),
        'last_author': String(source='metadata', indexed=False, stored=True),
        'title': Multilingual(source='metadata', indexed=True, stored=True),
        'description': Multilingual(source='metadata', indexed=True),
        'subject': Multilingual(source='metadata', indexed=True),
        # Key & class id
        'abspath': String(key_field=True, indexed=True, stored=True),
        'format': String(indexed=True, stored=True),
        # Folder's view
        'parent_path': String(indexed=True),
        'name': String(stored=True, indexed=True),
        # Referential integrity
        'links': String(multiple=True, indexed=True),
        # Full text search
        'text': Unicode(indexed=True),
        # Various classifications
        'is_role_aware': Boolean(indexed=True),
        'is_image': Boolean(indexed=True),
        'is_folder': Boolean(indexed=True),
        })


    @classmethod
    def get_property_datatype(cls, name, default=String):
        datatype = cls.class_schema.get(name)
        if datatype and getattr(datatype, 'source', None) == 'metadata':
            return datatype
        return default


    def has_property(self, name, language=None):
        return self.metadata.has_property(name, language=language)


    def _get_property(self, name, language=None):
        return self.metadata.get_property(name, language=language)


    def set_property(self, name, value, language=None):
        # Check the new value is different from the old value
        if language:
            old_value = self.get_property(name, language=language)
        else:
            old_value = self.get_property(name)

        if value == old_value:
            return

        # Set property
        if language:
            value = Property(value, lang=language)

        get_context().database.change_resource(self)
        self.metadata.set_property(name, value)


    def del_property(self, name):
        if self.has_property(name):
            get_context().database.change_resource(self)
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


    def get_last_author(self):
        revision = self.get_last_revision()
        return revision['username'] if revision else None


    def get_mtime(self):
        revision = self.get_last_revision()
        return revision['date'] if revision else None


    ########################################################################
    # Indexing
    ########################################################################
    def to_text(self):
        """This function must return:
           1) An unicode text.
            or
           2) A dict in a multilingual context:
              {'fr': u'....',
               'en': u'....' ....}
        """
        raise NotImplementedError


    def get_catalog_values(self):
        from access import RoleAware
        from file import Image
        from folder import Folder

        # Values
        abspath = self.get_canonical_path()
        # Get the languages
        site_root = self.get_site_root()
        languages = site_root.get_property('website_languages')

        # Titles
        title = {}
        for language in languages:
            title[language] = self.get_title(language=language)

        # Descriptions
        description = {}
        for language in languages:
            description[language] = self.get_property('description',
                                                      language=language)

        # Subjects (keywords)
        subject = {}
        for language in languages:
            subject[language] = self.get_property('subject',
                                                  language=language)

        # Full text
        context = get_context()
        text = None
        try:
            server = context.server
        except AttributeError:
            server = None
        if server is not None and server.index_text:
            try:
                text = self.to_text()
            except NotImplementedError:
                pass
            except Exception:
                # FIXME Use a different logger
                log_error('Indexation failed!', domain='ikaaro')
#                log = "%s failed" % self.get_abspath()
#               server.event_log.write(log)
#               server.event_log.flush()

        # Parent path
        parent_path = None
        abspath_str = str(abspath)
        if abspath_str != '/':
            parent_path = abspath.resolve2('..')
            parent_path = str(parent_path)

        # Workflow state
        if isinstance(self, WorkflowAware):
            workflow_state = self.get_workflow_state()
        else:
            workflow_state = None

        # Role Aware
        is_role_aware = isinstance(self, RoleAware)

        # Ok
        return {
            'name': self.name,
            'abspath': abspath_str,
            'format': self.metadata.format,
            'mtime': self.get_property('mtime'),
            'last_author': self.get_property('last_author'),
            'title': title,
            'subject': subject,
            'text': text,
            'links': self.get_links(),
            'parent_path': parent_path,
            # This should be defined by subclasses
            'is_image': isinstance(self, Image),
            'is_folder': isinstance(self, Folder),
            'is_role_aware': is_role_aware,
            'users': self.get_members() if is_role_aware else None,
            'workflow_state': workflow_state}


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
        """This method updates the links from/to other resources.  It is
        called when the resource has been moved and/or renamed.

        This method is called by 'Database._before_commit', the 'source'
        parameter is the place the resource has been moved from.
        """
        # (1) Update links to other resources
        self.update_relative_links(Path(source))

        # (2) Update resources that link to me
        database = get_context().database
        target = self.get_canonical_path()
        query = PhraseQuery('links', source)
        results = database.catalog.search(query).get_documents()
        for result in results:
            path = result.abspath
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
        # Action
        getattr(self, 'update_%s' % version)()

        # If the action removes the resource, we are done
        metadata = self.metadata
        if metadata.key is None:
            return

        # Update version
        metadata.set_changed()
        metadata.version = version


    ########################################################################
    # User interface
    ########################################################################
    def get_title(self, language=None):
        title = self.get_property('title', language=language)
        if title:
            return title
        # Fallback to the resource's name
        return unicode(self.name)


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
    commit_log = DBResource_CommitLog()
    changes = DBResource_Changes()
    backlinks = DBResource_Backlinks()
    http_put = Put_View()
    http_delete = Delete_View()

