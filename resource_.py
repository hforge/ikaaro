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
from pickle import dumps
from os.path import basename, dirname

# Import from itools
from itools.core import is_prototype, lazy
from itools.csv import Property
from itools.database import Resource, Metadata, register_field
from itools.database import AndQuery, NotQuery, PhraseQuery
from itools.datatypes import Boolean, DateTime, Integer, String, Unicode
from itools.gettext import MSG
from itools.handlers import Folder as FolderHandler
from itools.log import log_warning
from itools.uri import Path
from itools.web import BaseView, get_context

# Import from ikaaro
from autoadd import AutoAdd
from autoedit import AutoEdit
from autoform import CheckboxWidget
from datatypes import CopyCookie
from enumerates import Groups_Datatype
from exceptions import ConsistencyError
from fields import Char_Field, Datetime_Field, File_Field, HTMLFile_Field
from fields import Select_Field, Text_Field, Textarea_Field
from popup import DBResource_AddImage, DBResource_AddLink
from popup import DBResource_AddMedia
from resource_views import DBResource_Remove
from resource_views import DBResource_Links, DBResource_Backlinks
from resource_views import LoginView, LogoutView
from resource_views import Put_View, Delete_View
from resource_views import DBResource_GetFile, DBResource_GetImage
from rest import Rest_Login, Rest_Schema, Rest_Query
from rest import Rest_Create, Rest_Read, Rest_Update, Rest_Delete
from revisions_views import DBResource_CommitLog, DBResource_Changes
from utils import get_base_path_query



class Share_Field(Select_Field):

    title = MSG(u'Share')
    datatype = Groups_Datatype
    widget = CheckboxWidget
    multiple = True
    indexed = True


    def access(self, mode, resource):
        context = get_context()
        return context.root.is_allowed_to_share(context.user, resource)



class DBResource(Resource):

    class_version = '20071215'
    class_description = None
    class_icon16 = 'icons/16x16/resource.png'
    class_icon48 = 'icons/48x48/resource.png'
    class_views = []
    context_menus = []


    def __init__(self, metadata):
        self.metadata = metadata


    def __eq__(self, resource):
        if not isinstance(resource, DBResource):
            error = "cannot compare DBResource and %s" % type(resource)
            raise TypeError, error

        return self.abspath == resource.abspath


    def __ne__(self, node):
        return not self.__eq__(node)


    #######################################################################
    # API / Tree
    #######################################################################
    @property
    def database(self):
        return self.metadata.database


    @lazy
    def parent(self):
        abspath = self.abspath
        if len(abspath) == 0:
            return None
        return self.get_resource(abspath[:-1])


    @property
    def name(self):
        return self.abspath.get_name()


    def get_root(self):
        return self.get_resource('/')


    def get_pathto(self, resource):
        return self.abspath.get_pathto(resource.abspath)


    #######################################################################
    # API / Folderish
    #######################################################################
    __fixed_handlers__ = [] # Resources that cannot be removed


    @property
    def handler(self):
        cls = FolderHandler
        key = self.metadata.key[:-9]
        handler = self.database.get_handler(key, cls=cls, soft=True)
        if handler is None:
            handler = cls()
            self.database.push_phantom(key, handler)

        return handler


    def get_handlers(self):
        """Return all the handlers attached to this resource, except the
        metadata.
        """
        handlers = [self.handler]
        # Fields
        for name, field in self.get_fields():
            if issubclass(field, File_Field):
                value = field.get_value(self, name)
                if value is not None:
                    handlers.append(value)

        # Ok
        return handlers


    def _get_names(self):
        folder = self.handler
        return [ x[:-9] for x in folder.get_handler_names()
                 if x[-9:] == '.metadata' ]


    def get_names(self, path='.'):
        resource = self.get_resource(path)
        return resource._get_names()


    def get_resource(self, path, soft=False):
        if type(path) is not Path:
            path = Path(path)

        # 1. Get the metadata
        if path.is_absolute():
            abspath = path
        else:
            abspath = self.abspath.resolve2(path)

        return self.database.get_resource(abspath, soft=soft)


    def get_resources(self, path='.'):
        here = self.get_resource(path)
        for name in here._get_names():
            yield here.get_resource(name)


    def make_resource_name(self):
        max_id = -1
        for name in self.get_names():
            # Mixing explicit and automatically generated names is allowed
            try:
                id = int(name)
            except ValueError:
                continue
            if id > max_id:
                max_id = id

        return str(max_id + 1)


    def make_resource(self, name, cls, soft=False, **kw):
        # Automatic name
        if name is None:
            name = self.make_resource_name()

        # Make a resource somewhere else
        if '/' in name:
            path = dirname(name)
            name = basename(name)
            resource = self.get_resource(path)
            resource.make_resource(name, cls, soft=soft, **kw)
            return

        # Soft
        if soft is True:
            resource = self.get_resource(name, soft=True)
            if resource:
                return resource

        # Make the metadata
        metadata = Metadata(cls=cls)
        self.handler.set_handler('%s.metadata' % name, metadata)
        metadata.set_property('mtime', get_context().timestamp)
        # Initialize
        resource = self.get_resource(name)
        resource.init_resource(**kw)
        # Ok
        self.database.add_resource(resource)
        return resource


    def del_resource(self, name, soft=False, ref_action='restrict'):
        """ref_action allows to specify which action is done before deleting
        the resource.
        ref_action can take 2 values:
        - 'restrict' (default value): do an integrity check
        - 'force': do nothing
        """
        database = self.database
        resource = self.get_resource(name, soft=soft)
        if soft and resource is None:
            return

        # Referential action
        if ref_action == 'restrict':
            # Check referencial-integrity (FIXME Check sub-resources too)
            path = str(resource.abspath)
            query_base_path = get_base_path_query(path)
            query = AndQuery(PhraseQuery('links', path),
                             NotQuery(query_base_path))
            results = database.search(query)
            # A resource may have been updated in the same transaction,
            # so not yet reindexed: we need to check that the resource
            # really links.
            for referrer in results.get_resources():
                if path in referrer.get_links():
                    err = 'cannot delete, resource "%s" is referenced'
                    raise ConsistencyError, err % path
        elif ref_action == 'force':
            # Do not check referencial-integrity
            pass
        else:
            raise ValueError, 'Incorrect ref_action "%s"' % ref_action

        # Events, remove
        path = str(resource.abspath)
        database.remove_resource(resource)
        # Remove
        fs = database.fs
        for handler in resource.get_handlers():
            # Skip empty folders and phantoms
            if fs.exists(handler.key):
                database.del_handler(handler.key)
        self.handler.del_handler('%s.metadata' % name)
        # Clear cookie
        context = get_context()
        cut, paths = context.get_cookie('ikaaro_cp', datatype=CopyCookie)
        if path in paths:
            context.del_cookie('ikaaro_cp')


    def copy_resource(self, source, target):
        raise NotImplementedError


    def move_resource(self, source, target):
        raise NotImplementedError


    def traverse_resources(self):
        yield self
        for name in self._get_names():
            resource = self.get_resource(name)
            for x in resource.traverse_resources():
                yield x


    #######################################################################
    # API / Views
    #######################################################################
    def get_default_view_name(self):
        views = self.class_views
        if not views:
            return None
        context = get_context()
        for view_name in views:
            view = getattr(self, view_name, None)
            if context.is_access_allowed(self, view):
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
        if is_prototype(view, BaseView):
            context = get_context()
            view = view(resource=self, context=context) # bind
            return view

        return None


    def get_context_menus(self):
        return self.context_menus


    ########################################################################
    # Properties
    ########################################################################
    def get_value(self, name, language=None):
        field = self.get_field(name)
        if field is None:
            return None
        return field.get_value(self, name, language)


    def set_value(self, name, value, language=None, **kw):
        field = self.get_field(name)
        if field is None:
            raise ValueError, 'Field %s do not exist' % name
        return field.set_value(self, name, value, language, **kw)


    def get_value_title(self, name, language=None):
        field = self.get_field(name)
        if field is None:
            return None
        return field.get_value_title(self, name, language)


    def get_brain_value(self, name):
        brain = get_context().database.search(
            PhraseQuery('abspath', str(self.abspath))).get_documents()[0]
        return getattr(brain, name, None)


    def get_html_field_body_stream(self, name, language=None):
        """Utility method, returns the stream for the given html field.
        """
        # 1. Check it is an html-file field
        field = self.get_field(name)
        if not is_prototype(field, HTMLFile_Field):
            raise ValueError, 'expected html-file field'

        # 2. Get the handler
        handler = field.get_value(self, name, language)
        if not handler:
            handler = field.class_handler()

        # 3. Get the body
        body = handler.get_body()
        if not body:
            raise ValueError, 'html file does not have a body'
        return body.get_content_elements()


    def get_property(self, name, language=None):
        property = self.metadata.get_property(name, language=language)
        if property:
            return property

        field = self.get_field(name)
        if field is None:
            return None

        default = field.get_default()
        if field.multiple:
            return [ Property(x) for x in default ]
        return Property(default)


    # XXX Backwards compatibility
    set_property = set_value


    def get_page_title(self):
        return self.get_title()


    def init_resource(self, **kw):
        """Return a Metadata object with sensible default values.
        """
        # Ownership
        owner = self.get_field('owner')
        if owner:
            user = get_context().user
            if user:
                self.set_value('owner', str(user.abspath))

        # Keyword parameters
        for name, value in kw.items():
            field = self.get_field(name)
            if field is None:
                raise ValueError, 'undefined field "%s"' % name
            if type(value) is dict:
                for lang in value:
                    field._set_value(self, name, value[lang], lang)
            else:
                field._set_value(self, name, value)


    def load_handlers(self):
        self.get_handlers()


    ########################################################################
    # Fields
    ########################################################################
    mtime = Datetime_Field(indexed=True, stored=True, readonly=True)
    last_author = Char_Field(indexed=False, stored=True, readonly=True)
    title = Text_Field(indexed=True, stored=True, title=MSG(u'Title'))
    description = Textarea_Field(indexed=True, title=MSG(u'Description'),
                                 hidden_by_default=True)
    subject = Text_Field(indexed=True, title=MSG(u'Keywords'),
                         hidden_by_default=True)
    share = Share_Field

    @property
    def is_content(self):
        return self.parent.is_content


    def has_property(self, name, language=None):
        return self.metadata.has_property(name, language=language)


    def del_property(self, name):
        if self.has_property(name):
            self.database.change_resource(self)
            self.metadata.del_property(name)


    ########################################################################
    # Versioning
    ########################################################################
    def get_files_to_archive(self, content=False):
        metadata = self.metadata.key
        if content is True:
            folder = self.handler.key
            return [metadata, folder]
        return [metadata]


    def get_revisions(self, n=None, content=False, author_pattern=None,
                      grep_pattern=None):
        if self.parent is None and content is True:
            files = None
        else:
            files = self.get_files_to_archive(content)

        worktree = self.database.worktree
        return worktree.git_log(files, n, author_pattern, grep_pattern)


    def get_owner(self):
        return self.get_value('owner')


    def get_share(self):
        return self.get_value('share')


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

        # Step 1. Automatically index fields
        languages = self.get_root().get_value('website_languages')
        for name, field in self.get_fields():
            if not field.indexed and not field.stored:
                continue

            if field.multilingual:
                value = {}
                for language in languages:
                    value[language] = field.get_value(self, name, language)
                values[name] = value
            else:
                values[name] = field.get_value(self, name)

        # Step 2. Index non-metadata properties
        # Path related fields
        abspath = self.abspath
        values['abspath'] = str(abspath)
        n = len(abspath)
        values['abspath_depth'] = n
        if n:
            values['parent_paths'] = [ str(abspath[:i]) for i in range(n) ]

        values['name'] = self.name
        values['is_content'] = self.is_content

        # Class related fields
        values['format'] = self.metadata.format
        values['base_classes'] = []
        for cls in self.__class__.__mro__:
            class_id = getattr(cls, 'class_id', None)
            if class_id:
                values['base_classes'].append(class_id)

        # Links to other resources
        values['owner'] = self.get_owner()
        values['share'] = self.get_share()
        values['links'] = list(self.get_links())

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

        # Time events
        reminder, payload = self.next_time_event()
        values['next_time_event'] = reminder
        values['next_time_event_payload'] = dumps(payload)

        # Ok
        return values


    #######################################################################
    # Time events
    #######################################################################
    def next_time_event(self):
        return None, None


    def time_event(self, payload):
        raise NotImplementedError


    #######################################################################
    # API
    #######################################################################
    def rename_handlers(self, new_name):
        """Consider we want to rename this resource to the given 'new_name',
        return the old a new names for all the attached handlers (except the
        metadata).

        This method is required by the "move_resource" method.
        """
        langs = self.get_resource('/').get_value('website_languages')

        aux = [(self.name, new_name)]
        for field_name in self.fields:
            field = self.get_field(field_name)
            if field and issubclass(field, File_Field):
                old = '%s.%s' % (self.name, field_name)
                new = '%s.%s' % (new_name, field_name)
                if field.multilingual:
                    for language in langs:
                        aux.append(('%s.%s' % (old, language),
                                    '%s.%s' % (new, language)))
                else:
                    aux.append((old, new))

        return aux


    def _on_move_resource(self, source):
        """This method updates the links from/to other resources.  It is
        called when the resource has been moved and/or renamed.

        This method is called by 'Database._before_commit', the 'source'
        parameter is the place the resource has been moved from.
        """
        # (1) Update links to other resources
        self.update_incoming_links(Path(source))

        # (2) Update resources that link to me
        database = self.database
        target = self.abspath
        query = PhraseQuery('links', source)
        results = database.search(query).get_documents()
        for result in results:
            path = result.abspath
            path = database.resources_old2new.get(path, path)
            resource = self.get_resource(path)
            resource.update_links(source, target)


    def get_links(self):
        # Automatically from the fields
        languages = self.get_resource('/').get_value('website_languages')
        links = set()
        for field_name in self.fields:
            field = self.get_field(field_name)
            if field:
                field.get_links(links, self, field_name, languages)

        # Support for dynamic models
        class_id = self.metadata.format
        if class_id[0] == '/':
            links.add(class_id)

        # Ok
        return links


    def update_links(self, source, target):
        """The resource identified by 'source' is going to be moved to
        'target'.  Update our links to it.

        The parameters 'source' and 'target' are absolute 'Path' objects.
        """
        base = str(self.abspath)
        old_base = self.database.resources_new2old.get(base, base)
        old_base = Path(old_base)
        new_base = Path(base)
        languages = self.get_resource('/').get_value('website_languages')

        for field_name in self.fields:
            field = self.get_field(field_name)
            if field:
                field.update_links(self, field_name, source, target,
                                   languages, old_base, new_base)

        self.database.change_resource(self)


    def update_incoming_links(self, source):
        """Update the relative links coming out from this resource after it
        was moved, so they are not broken. The old path is in parameter. The
        new path is "self.abspath".
        """
        languages = self.get_resource('/').get_value('website_languages')
        for field_name in self.fields:
            field = self.get_field(field_name)
            if field:
                field.update_incoming_links(self, field_name, source,
                                            languages)


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


    #######################################################################
    # Icons
    #######################################################################
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


    #######################################################################
    # User interface
    #######################################################################
    def get_views(self):
        context = get_context()
        for name in self.class_views:
            view_name = name.split('?')[0]
            view = self.get_view(view_name)
            if context.is_access_allowed(self, view):
                yield name, view


    def get_title(self, language=None):
        title = self.get_value('title', language=language)
        if title:
            return title
        # Fallback to the resource's name
        return unicode(self.name)


    def get_edit_languages(self, context):
        root = self.get_root()
        site_languages = root.get_value('website_languages')
        default = root.get_default_edit_languages()

        # Can not use context.query[] because edit_language is not necessarily
        # defined
        datatype = String(multiple=True, default=default)
        edit_languages = context.get_query_value('edit_language', datatype)
        edit_languages = [ x for x in edit_languages if x in site_languages ]

        return edit_languages if edit_languages else default


    #######################################################################
    # Cut & Paste Resources
    #######################################################################
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
    new_instance = AutoAdd(fields=['title', 'location'])
    edit = AutoEdit(fields=['title', 'description', 'subject', 'share'])
    remove = DBResource_Remove
    get_file = DBResource_GetFile
    get_image = DBResource_GetImage
    # Login/Logout
    login = LoginView
    logout = LogoutView
    # Popups
    add_image = DBResource_AddImage
    add_link = DBResource_AddLink
    add_media = DBResource_AddMedia
    # Commit log
    commit_log = DBResource_CommitLog
    changes = DBResource_Changes
    # Links
    backlinks = DBResource_Backlinks
    links = DBResource_Links
    # External editor
    http_put = Put_View
    http_delete = Delete_View
    # Rest (web services)
    rest_login = Rest_Login
    rest_query = Rest_Query
    rest_create = Rest_Create
    rest_read = Rest_Read
    rest_update = Rest_Update
    rest_delete = Rest_Delete
    rest_schema = Rest_Schema


###########################################################################
# Register read-only fields
###########################################################################

# Path related fields
register_field('abspath', String(indexed=True, stored=True))
register_field('abspath_depth', Integer(indexed=True, stored=True))
register_field('parent_paths', String(multiple=True, indexed=True))
register_field('name', String(stored=True, indexed=True))
# Class related fields
register_field('format', String(indexed=True, stored=True))
register_field('base_classes', String(multiple=True, indexed=True))
# Referential integrity
register_field('links', String(multiple=True, indexed=True))
# Full text search
register_field('text', Unicode(indexed=True))
# Various classifications
register_field('is_content', Boolean(indexed=True))
# Time events
register_field('next_time_event', DateTime(stored=True))
register_field('next_time_event_payload', String(stored=True))
