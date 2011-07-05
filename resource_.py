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
from itools.datatypes import Boolean, DateTime, Integer, String, URI, Unicode
from itools.gettext import MSG
from itools.log import log_warning
from itools.uri import Path
from itools.web import AccessControl, BaseView, get_context
from itools.database import PhraseQuery, Resource

# Import from ikaaro
from autoform import MultilineWidget
from datatypes import Multilingual
from popup import DBResource_AddImage, DBResource_AddLink
from popup import DBResource_AddMedia
from registry import register_resource_class
from resource_views import DBResource_Edit, DBResource_Backlinks
from resource_views import DBResource_Links, LoginView, LogoutView
from resource_views import Put_View, Delete_View
from revisions_views import DBResource_CommitLog, DBResource_Changes
from utils import split_reference
from views_new import NewInstance
from workflow import WorkflowAware



class FreeDatatype(String):
    """This datatype is used for properties not defined in the resource
    schema, when the schema is defined as extensible.
    """

    multiple = True
    parameters_schema = freeze({})
    parameters_schema_default = String(multiple=True)



class DBResourceMetaclass(type):

    def __new__(mcs, name, bases, dict):
        cls = type.__new__(mcs, name, bases, dict)
        if 'class_id' in dict:
            register_resource_class(cls)
        for name, dt in cls.class_schema.iteritems():
            if getattr(dt, 'indexed', False) or getattr(dt, 'stored', False):
                register_field(name, dt)
        return cls



class DBResource(Resource):

    __metaclass__ = DBResourceMetaclass
    __hash__ = None

    class_views = []
    context_menus = []


    def __init__(self, metadata):
        self.metadata = metadata
        self._handler = None
        # The tree
        self.name = ''
        self.parent = None


    def _get_names(self):
        raise NotImplementedError


    def _get_resource(self, name):
        return None


    def __eq__(self, resource):
        if not isinstance(resource, DBResource):
            raise TypeError, "cannot compare DBResource and %s" % type(resource)
        return self.get_canonical_path() == resource.get_canonical_path()


    def __ne__(self, node):
        return not self.__eq__(node)


    #######################################################################
    # API / Tree
    #######################################################################
    def get_abspath(self):
        if self.parent is None:
            return Path('/')
        parent_path = self.parent.get_abspath()

        return parent_path.resolve_name(self.name)

    abspath = property(get_abspath)


    def get_canonical_path(self):
        if self.parent is None:
            return Path('/')
        parent_path = self.parent.get_canonical_path()

        return parent_path.resolve_name(self.name)


    def get_real_resource(self):
        cpath = self.get_canonical_path()
        if cpath == self.get_abspath():
            return self
        return self.get_resource(cpath)


    def get_root(self):
        if self.parent is None:
            return self
        return self.parent.get_root()


    def get_pathto(self, resource):
        # XXX brain.abspath is the canonical path
        # not the possible virtual path
        return self.get_abspath().get_pathto(resource.abspath)


    def get_names(self, path='.'):
        resource = self.get_resource(path)
        return resource._get_names()


    def get_resource(self, path, soft=False):
        if type(path) is not Path:
            path = Path(path)

        if path.is_absolute():
            here = self.get_root()
        else:
            here = self

        while path and path[0] == '..':
            here = here.parent
            path = path[1:]

        for name in path:
            resource = here._get_resource(name)
            if resource is None:
                if soft is True:
                    return None
                raise LookupError, 'resource "%s" not found' % path
            resource.parent = here
            resource.name = name
            here = resource

        return here


    def get_resources(self, path='.'):
        here = self.get_resource(path)
        for name in here._get_names():
            resource = here._get_resource(name)
            resource.parent = here
            resource.name = name
            yield resource


    def del_resource(self, path, soft=False):
        raise NotImplementedError


    def copy_resource(self, source, target):
        raise NotImplementedError


    def move_resource(self, source, target):
        raise NotImplementedError


    def traverse_resources(self):
        yield self


    def get_site_root(self):
        from website import WebSite
        resource = self
        while not isinstance(resource, WebSite):
            resource = resource.parent
        return resource


    #######################################################################
    # API / Views
    #######################################################################
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


    def get_view(self, name, query=None):
        # To define a default view, override this
        if name is None:
            name = self.get_default_view_name()
            if name is None:
                return None

        # Explicit view, defined by name
        view = getattr(self, name, None)
        if view is None or not isinstance(view, BaseView):
            return None

        return view

    def get_context_menus(self):
        return self.context_menus


    #######################################################################
    # API / Security
    #######################################################################
    def get_access_control(self):
        resource = self
        while resource is not None:
            if isinstance(resource, AccessControl):
                return resource
            resource = resource.parent

        return None


    ########################################################################
    # Properties
    ########################################################################
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


    def get_page_title(self):
        return self.get_title()


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
            cls = getattr(self, 'class_handler', None)
            if cls is None:
                return None
            database = self.metadata.database
            key = self.metadata.key[:-9]
            handler = database.get_handler(key, cls=cls, soft=True)
            if handler is None:
                handler = cls()
                database.push_phantom(key, handler)

            self._handler = handler
        return self._handler

    handler = property(get_handler)


    def load_handlers(self):
        self.get_handlers()


    ########################################################################
    # Metadata
    ########################################################################
    class_schema_extensible = False
    class_schema = freeze({
        # Metadata
        'mtime': DateTime(source='metadata', indexed=True, stored=True),
        'last_author': String(source='metadata', indexed=False, stored=True),
        'title': Multilingual(source='metadata', indexed=True, stored=True,
                              title=MSG(u'Title')),
        'description': Multilingual(source='metadata', indexed=True,
                                    title=MSG(u'Description'),
                                    widget=MultilineWidget),
        'subject': Multilingual(source='metadata', indexed=True),
        # Key & class id
        'abspath': String(indexed=True, stored=True),
        'abspath_depth': Integer(indexed=True, stored=True),
        'format': String(indexed=True, stored=True),
        # Folder's view
        'parent_paths': String(multiple=True, indexed=True),
        'name': String(stored=True, indexed=True),
        # Referential integrity
        'links': String(multiple=True, indexed=True),
        # Full text search
        'text': Unicode(indexed=True),
        # Various classifications
        'is_role_aware': Boolean(indexed=True),
        'is_image': Boolean(indexed=True),
        'is_folder': Boolean(indexed=True),
        'is_content': Boolean(indexed=True),
        })


    @property
    def is_content(self):
        return self.parent.is_content


    @classmethod
    def get_property_datatype(cls, name):
        datatype = cls.class_schema.get(name)
        if datatype and getattr(datatype, 'source', None) == 'metadata':
            return datatype
        if cls.class_schema_extensible:
            return FreeDatatype
        msg = 'in class "{0}" unexpected property "{1}"'
        raise ValueError, msg.format(cls, name)


    def has_property(self, name, language=None):
        return self.metadata.has_property(name, language=language)


    def _get_property(self, name, language=None):
        return self.metadata.get_property(name, language=language)


    def set_property(self, name, value, language=None):
        """If value == old value then return False
           else make the change and return True
        """

        # Check the new value is different from the old value
        old_value = self.get_property(name, language=language)

        if value == old_value:
            return False

        # Set property
        if language:
            value = Property(value, lang=language)

        get_context().database.change_resource(self)
        self.metadata.set_property(name, value)

        return True


    def del_property(self, name):
        if self.has_property(name):
            get_context().database.change_resource(self)
            self.metadata.del_property(name)


    ########################################################################
    # Versioning
    ########################################################################
    def get_files_to_archive(self, content=False):
        raise NotImplementedError


    def get_revisions(self, n=None, content=False, author_pattern=None,
                      grep_pattern=None):
        if self.parent is None and content is True:
            files = None
        else:
            files = self.get_files_to_archive(content)

        database = get_context().database
        return database.get_revisions(files, n, author_pattern, grep_pattern)


    def get_last_revision(self):
        files = self.get_files_to_archive()
        database = get_context().database
        return database.get_last_revision(files)


    def get_owner(self):
        revisions = self.get_revisions()
        if not revisions:
            return None
        return revisions[-1]['username']


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
        values = {}

        # Step 1. Automatically index metadata properties
        languages = self.get_site_root().get_property('website_languages')
        schema = self.class_schema
        for name in schema:
            datatype = schema[name]
            indexed = getattr(datatype, 'indexed', False)
            stored = getattr(datatype, 'stored', False)
            if not indexed and not stored:
                continue

            # Skip non-metadata sources
            source = getattr(datatype, 'source', None)
            if source != 'metadata':
                # TODO We should have a hook here (to avoid Step 2)
                continue

            # Metadata properties
            multilingual = getattr(datatype, 'multilingual', False)
            if multilingual:
                value = {}
                for language in languages:
                    value[language] = self.get_property(name, language)
                values[name] = value
            else:
                values[name] = self.get_property(name)

        # Step 2. Index non-metadata properties
        values['name'] = self.name
        values['format'] = self.metadata.format
        links = self.get_links()
        if type(links) is list: # TODO 'get_links' must return <set>
            links = set(links)
        values['links'] = list(links)

        # Parent path
        abspath = self.get_canonical_path()
        abspath_str = str(abspath)
        if abspath_str != '/':
            values['parent_paths'] = [ str(abspath[:i])
                                       for i in range(len(abspath)) ]
        values['abspath'] = abspath_str
        values['abspath_depth'] = len(abspath)

        # Full text
        context = get_context()
        try:
            server = context.server
        except AttributeError:
            server = None
        if server is not None and server.index_text:
            try:
                values['text'] = self.to_text()
            except NotImplementedError:
                pass
            except Exception:
                log = 'Indexation failed: %s' % abspath
                log_warning(log, domain='ikaaro')

        # Workflow state
        if isinstance(self, WorkflowAware):
            values['workflow_state'] = self.get_workflow_state()

        # Image
        from file import Image
        values['is_image'] = isinstance(self, Image)

        # Folder
        from folder import Folder
        values['is_folder'] = isinstance(self, Folder)

        # Content
        values['is_content'] = self.is_content

        # Ok
        return values


    ########################################################################
    # API
    ########################################################################
    def get_handlers(self):
        """Return all the handlers attached to this resource, except the
        metadata.
        """
        handler = self.handler
        if handler is None:
            return []
        return [handler]


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


    def _get_references_from_schema(self):
        """Returns the names of properties that are references to other
        resources.

        TODO This list should be calculated statically to avoid a performance
        hit at run time.
        """
        schema = self.class_schema
        for name in schema:
            datatype = schema[name]
            if issubclass(datatype, URI):
                source = getattr(datatype, 'source', None)
                if source != 'metadata':
                    raise ValueError, 'schema error'
                yield name


    def get_links(self):
        links = set()
        base = self.get_canonical_path()
        site_root = self.get_site_root()
        available_languages = site_root.get_property('website_languages')

        schema = self.class_schema
        for name in self._get_references_from_schema():
            datatype = schema[name]
            multiple = getattr(datatype, 'multiple', False)
            if getattr(datatype, 'multilingual', False):
                languages = available_languages
            else:
                languages = [ None ]

            for lang in languages:
                prop = self.metadata.get_property(name, language=lang)
                if prop is None:
                    continue
                if multiple:
                    # Multiple
                    for x in prop:
                        value = x.value
                        if not value:
                            continue
                        # Get the reference, path and view
                        ref, path, view = split_reference(value)
                        if ref.scheme:
                            continue
                        link = base.resolve2(path)
                        links.add(str(link))
                else:
                    value = prop.value
                    if not value:
                        continue
                    # Get the reference, path and view
                    ref, path, view = split_reference(value)
                    if ref.scheme:
                        continue
                    # Singleton
                    link = base.resolve2(path)
                    links.add(str(link))

        return links


    def update_links(self, source, target):
        """The resource identified by 'source' is going to be moved to
        'target'.  Update our links to it.

        The parameters 'source' and 'target' are absolute 'Path' objects.
        """
        database = get_context().database

        base = self.get_canonical_path()
        base = str(base)
        old_base = database.resources_new2old.get(base, base)
        old_base = Path(old_base)
        new_base = Path(base)
        site_root = self.get_site_root()
        available_languages = site_root.get_property('website_languages')

        schema = self.class_schema
        for name in self._get_references_from_schema():
            datatype = schema[name]
            multiple = getattr(datatype, 'multiple', False)
            if getattr(datatype, 'multilingual', False):
                languages = available_languages
            else:
                languages = [ None ]

            for lang in languages:
                prop = self.metadata.get_property(name, language=lang)
                if prop is None:
                    continue
                if multiple:
                    # Multiple
                    new_values = []
                    for p in prop:
                        value = p.value
                        if not value:
                            continue
                        # Get the reference, path and view
                        ref, path, view = split_reference(value)
                        if ref.scheme:
                            continue
                        path = old_base.resolve2(path)
                        if path == source:
                            # Explicitly call str because URI.encode does
                            # nothing
                            new_value = str(new_base.get_pathto(target)) + view
                            new_values.append(new_value)
                        else:
                            new_values.append(p)
                    self.set_property(name, new_values, lang)
                else:
                    # Singleton
                    value = prop.value
                    if not value:
                        continue
                    # Get the reference, path and view
                    ref, path, view = split_reference(value)
                    if ref.scheme:
                        continue
                    path = old_base.resolve2(path)
                    if path == source:
                        # Hit the old name
                        # Build the new reference with the right path
                        # Explicitly call str because URI.encode does nothing
                        new_value = str(new_base.get_pathto(target)) + view
                        self.set_property(name, new_value, lang)

        database.change_resource(self)


    def update_relative_links(self, source):
        """Update the relative links coming out from this resource after it
        was moved, so they are not broken. The old path is in parameter. The
        new path is "self.get_canonical_path()".
        """
        target = self.get_canonical_path()
        resources_old2new = get_context().database.resources_old2new
        site_root = self.get_site_root()
        available_languages = site_root.get_property('website_languages')

        schema = self.class_schema
        for name in self._get_references_from_schema():
            datatype = schema[name]
            languages = [ None ]
            multiple = getattr(datatype, 'multiple', False)
            if getattr(datatype, 'multilingual', False):
                languages = available_languages
            for lang in languages:
                prop = self.metadata.get_property(name, language=lang)
                if prop is None:
                    continue
                if multiple:
                    # Multiple
                    new_values = []
                    for p in prop:
                        value = p.value
                        if not value:
                            continue
                        # Get the reference, path and view
                        ref, path, view = split_reference(value)
                        if ref.scheme:
                            continue
                        # Calculate the old absolute path
                        old_abs_path = source.resolve2(path)
                        # Check if the target path has not been moved
                        new_abs_path = resources_old2new.get(old_abs_path,
                                                             old_abs_path)
                        new_value = str(target.get_pathto(new_abs_path)) + view
                        new_values.append(new_value)
                    self.set_property(name, new_values, lang)
                else:
                    # Singleton
                    value = prop.value
                    if not value:
                        continue
                    # Get the reference, path and view
                    ref, path, view = split_reference(value)
                    if ref.scheme:
                        continue
                    # Calculate the old absolute path
                    old_abs_path = source.resolve2(path)
                    # Check if the target path has not been moved
                    new_abs_path = resources_old2new.get(old_abs_path,
                                                         old_abs_path)

                    # Explicitly call str because URI.encode does nothing
                    new_value = str(target.get_pathto(new_abs_path)) + view
                    self.set_property(name, new_value, lang)


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


    def get_title(self, language=None):
        title = self.get_property('title', language=language)
        if title:
            return title
        # Fallback to the resource's name
        return unicode(self.name)


    def get_edit_languages(self, context):
        site_root = self.get_site_root()
        site_languages = site_root.get_property('website_languages')
        default = site_root.get_default_edit_languages()

        # Can not use context.query[] because edit_language is not necessarily
        # defined
        datatype = String(multiple=True, default=default)
        edit_languages = context.get_query_value('edit_language', datatype)
        edit_languages = [ x for x in edit_languages if x in site_languages ]

        return edit_languages if edit_languages else default


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
    links = DBResource_Links()
    http_put = Put_View()
    http_delete = Delete_View()
