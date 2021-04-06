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
from logging import getLogger
from pickle import dumps
from uuid import uuid4

# Import from itools
from ikaaro.datatypes import HTMLBody
from itools.core import is_prototype, lazy
from itools.database import MetadataProperty
from itools.database import Resource, register_field
from itools.database import PhraseQuery
from itools.datatypes import DateTime, Date, Decimal
from itools.datatypes import Integer, String, Unicode
from itools.gettext import MSG
from itools.handlers import Folder as FolderHandler
from itools.uri import Path
from itools.web import ItoolsView, get_context

# Import from ikaaro
from autoadd import AutoAdd
from autoedit import AutoEdit
from enumerates import Groups_Datatype
from fields import File_Field, HTMLFile_Field
from fields import SelectAbspath_Field, UUID_Field
from fields import CTime_Field, MTime_Field, LastAuthor_Field
from fields import Title_Field, Description_Field, Subject_Field
from fields import URI_Field
from popup import DBResource_AddImage, DBResource_AddLink
from popup import DBResource_AddMedia
from resource_views import AutoJSONResourceExport
from resource_views import AutoJSONResourcesImport
from resource_views import DBResource_Remove
from resource_views import DBResource_Links, DBResource_Backlinks
from resource_views import LoginView, LogoutView
from resource_views import DBResource_GetFile, DBResource_GetImage
from update import class_version_to_date
from utils import get_resource_by_uuid_query
from widgets import CheckboxWidget
from widgets import RTEWidget


log = getLogger("ikaaro")


class Share_Field(SelectAbspath_Field):

    title = MSG(u'Share')
    datatype = Groups_Datatype()
    widget = CheckboxWidget
    multiple = True
    indexed = True


    def access(self, mode, resource):
        context = get_context()
        return context.root.is_allowed_to_share(context.user, resource)



class DBResource(Resource):

    class_version = '20071215'
    class_description = None
    class_icon_css = 'fa-pencil-alt'
    class_views = []

    # Internal
    _values = {}
    _values_title = {}
    _metadata = None
    _brain = None

    # Config
    context_menus = []

    # Fields
    uuid = UUID_Field()
    ctime = CTime_Field()
    mtime = MTime_Field()
    last_author = LastAuthor_Field()
    title = Title_Field()
    description = Description_Field()
    subject = Subject_Field()
    share = Share_Field()


    def __init__(self, abspath, database, metadata=None, brain=None):
        self.abspath = abspath
        self.database = database
        self._metadata = metadata
        self._brain = brain
        self._values = {}
        self._values_title = {}


    def __eq__(self, resource):
        if resource is None:
            return False
        if not isinstance(resource, DBResource):
            error = "cannot compare DBResource and %s" % type(resource)
            raise TypeError(error)
        return self.abspath == resource.abspath


    def __ne__(self, node):
        return not self.__eq__(node)


    #######################################################################
    # API / Tree
    #######################################################################
    @lazy
    def metadata(self):
        if self._metadata:
            return self._metadata
        self._metadata = self.database.get_metadata(self.abspath)
        return self._metadata


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
            self.database.push_handler(key, handler)
        return handler


    def get_handlers(self):
        """Return all the handlers attached to this resource, except the
        metadata.
        """
        handlers = [self.handler]
        return handlers + self.get_fields_handlers()


    def get_fields_handlers(self):
        handlers = []
        root = self.get_root()
        langs = root.get_value('website_languages')
        # Fields
        for name, field in self.get_fields():
            if is_prototype(field, File_Field):
                if field.multilingual:
                    for language in langs:
                        value = field.get_value(self, name, language)
                        if value is not None:
                            handlers.append(value)
                else:
                    value = field.get_value(self, name)
                    if value is not None:
                        handlers.append(value)
        # Ok
        return handlers


    def get_resource(self, path, soft=False):
        if type(path) is not Path:
            path = Path(path)

        # 1. Get the metadata
        if path.is_absolute():
            abspath = path
        else:
            abspath = self.abspath.resolve2(path)
        try:
            return self.database.get_resource(abspath, soft=soft)
        except Exception as e:
            log.error(
                "Could not retrieve the resource {}".format(abspath),
                exc_info=True
            )
            raise


    #######################################################################
    # Resource API
    #######################################################################

    def get_resources(self):
        for name in self._get_names():
            yield self.get_resource(name)


    def get_resource_by_uuid(self, uuid, context,
            bases_class_id=None, class_id=None):
        # Get query
        query = get_resource_by_uuid_query(uuid, bases_class_id, class_id)
        search = context.database.search(query)
        # Return resource
        if not search:
            return None
        return search.get_resources(size=1).next()


    def make_resource_name(self):
        raise NotImplementedError


    def make_resource(self, name, cls, soft=False, **kw):
        raise NotImplementedError


    def del_resource(self, name, soft=False, ref_action='restrict'):
        raise NotImplementedError


    def copy_resource(self, source, target, check_if_authorized=True):
        raise NotImplementedError


    def move_resource(self, source, target, check_if_authorized=True):
        raise NotImplementedError


    def traverse_resources(self):
        yield self

    def _get_names(self):
        return []


    def get_names(self, path='.'):
        resource = self.get_resource(path)
        return resource._get_names()


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
        if is_prototype(view, ItoolsView):
            context = get_context()
            view = view(resource=self, context=context) # bind
            return view

        return None


    def get_context_menus(self):
        return self.context_menus


    ########################################################################
    # Properties
    ########################################################################
    def check_if_context_exists(self):
        """ We cannot do:
          - resource.get_value(xxx)
          - resource.set_value('name', xxx)
        if there's no context.
        """
        context = get_context()
        if context is None:
            raise ValueError('Error: No context was defined')


    def get_value(self, name, language=None):
        field = self.get_field(name)
        if field is None:
            msg = 'field {name} is not defined on {class_id}'
            log.warning(msg.format(name=name, class_id=self.class_id))
            return None
        # Check context
        self.check_if_context_exists()
        # Check if field is obsolete
        if field.obsolete:
            msg = 'field {name} is obsolete on {class_id}'
            log.warning(msg.format(name=name, class_id=self.class_id))
        # TODO: Use decorator for cache
        # TODO: Reactivate when ready
        #cache_key = (name, language)
        #if self._values.has_key(cache_key):
        #    return self._values[cache_key]
        if self._brain and field.stored and not is_prototype(field.datatype, Decimal):
            try:
                value = self.get_value_from_brain(name, language)
            except Exception as e:
                # FIXME Sometimes we cannot get value from brain
                # We're tying to debug this problem
                msg = 'Warning: cannot get value from brain {0} {1}'
                msg = msg.format(self.abspath, name)
                log.warning(msg)
                value = field.get_value(self, name, language)
        else:
            value = field.get_value(self, name, language)
        #self._values[cache_key] = value
        return value


    def get_value_from_brain(self, name, language=None):
        # If brain is loaded & field is stored get value from xapian
        field = self.get_field(name)
        brain_value = self._brain.get_value(name, language)
        if type(brain_value) is datetime:
            # Fix tzinfo for datetime values
            context = get_context()
            value = context.fix_tzinfo(brain_value)
        else:
            value = brain_value
        value = value or field.default
        if value is None:
            # Xapian do not index default value
            value = field.get_value(self, name, language)
        return value


    def set_value(self, name, value, language=None, **kw):
        self.check_if_context_exists()
        field = self.get_field(name)
        if field is None:
            raise ValueError('Field %s do not exist' % name)
        if field.multilingual and language is None and not isinstance(value, MSG):
            raise ValueError('Field %s is multilingual' % name)
        # TODO: Use decorator for cache
        self.clear_cache(name, language)
        # Set value
        return field.set_value(self, name, value, language, **kw)


    def clear_cache(self, name, language):
        cache_key = (name, language)
        if self._values.get(cache_key):
            del self._values[cache_key]
        if self._values_title.get(cache_key):
            del self._values_title[cache_key]
        self._brain = None


    def get_value_title(self, name, language=None, mode=None):
        # TODO: Use decorator for cache
        # TODO: Reactivate when ready
        #cache_key = (name, language)
        #if (self._values_title.has_key(cache_key) and
        #    self._values_title[cache_key].has_key(mode)):
        #    return self._values_title[cache_key][mode]
        field = self.get_field(name)
        if field is None:
            return None
        value_title = field.get_value_title(self, name, language, mode)
        #self._values_title.setdefault(cache_key, {})[mode] = value_title
        return value_title


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
            raise ValueError('expected html-file field')

        # 2. Get the handler
        handler = field.get_value(self, name, language)
        if not handler:
            handler = field.class_handler()

        # 3. Get the body
        body = handler.get_body()
        if not body:
            raise ValueError('html file does not have a body')
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
            return [ MetadataProperty(x, None) for x in default ]
        return MetadataProperty(default, None)


    # XXX Backwards compatibility
    set_property = set_value


    def get_page_title(self):
        return self.get_title()


    def init_resource(self, **kw):
        """Return a Metadata object with sensible default values.
        """
        context = get_context()
        user = context.user
        now = context.timestamp
        # UUID
        self.set_uuid()
        # Ctime
        if 'ctime' not in kw:
            self.set_value('ctime', now)
        # Mtime
        if 'mtime' not in kw:
            self.set_value('mtime', now)
        # Last author
        if 'last_author' not in kw and user:
            self.set_value('last_author', user.name)
        # Ownership
        owner = self.get_field('owner', soft=True)
        if owner and user:
            self.set_value('owner', str(user.abspath))

        # Keyword parameters
        for name, value in kw.items():
            field = self.get_field(name)
            if field is None:
                raise ValueError('undefined field "%s"' % name)
            if type(value) is dict:
                for lang in value:
                    field._set_value(self, name, value[lang], lang)
            else:
                field._set_value(self, name, value)


    def set_uuid(self):
        self.set_value('uuid', uuid4().hex)


    def update_resource(self, context):
        """ Method called every time the resource is changed"""
        pass


    def load_handlers(self):
        self.get_handlers()



    def has_property(self, name, language=None):
        return self.metadata.has_property(name, language=language)


    def del_property(self, name):
        if self.has_property(name):
            self.reindex()
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

        backend = self.database.backend
        return backend.git_log(files, n, author_pattern, grep_pattern)


    def get_owner(self):
        if self.get_field('owner'):
            return self.get_value('owner')
        return None


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
        return None


    def get_catalog_values(self):
        values = {}
        # Step 1. Automatically index fields
        root = self.get_root()
        languages = root.get_value('website_languages')
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
        # Class related fields
        values['format'] = self.metadata.format
        values['base_classes'] = self.get_base_classes()
        values['class_version'] = class_version_to_date(self.metadata.version)
        # Links to other resources
        values['owner'] = self.get_owner()
        values['share'] = self.get_share()
        values['links'] = list(self.get_links())
        values['onchange_reindex'] = self.get_onchange_reindex()
        # Full text indexation (not available in icms-init.py FIXME)
        context = get_context()
        server = context.server
        if server and server.index_text:
            try:
                values['text'] = self.to_text()
            except Exception as e:
                log.error("Indexation failed: {}".format(abspath), exc_info=True)
        # Time events for the CRON
        reminder, payload = self.next_time_event()
        values['next_time_event'] = reminder
        if payload:
            values['next_time_event_payload'] = dumps(payload)
        else:
            values['next_time_event_payload'] = None
        # Ok
        return values


    def get_onchange_reindex(self):
        return None


    def get_base_classes(self):
        l = []
        for cls in self.__class__.__mro__:
            class_id = getattr(cls, 'class_id', None)
            if class_id:
                l.append(class_id)
        return l

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

        aux = []
        for field_name in self.fields:
            field = self.get_field(field_name)
            if field and is_prototype(field, File_Field):
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
        self.reindex()


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
        """
        Update the ressource to a new version.
        :param version: The target version
        """
        # Action
        getattr(self, 'update_%s' % version)()
        # If the action removes the resource, we are done
        metadata = self.metadata
        if metadata.key is None:
            return
        # Update version
        metadata.set_changed()
        metadata.version = version
        # Set resource as changed (to reindex class_version)
        self.reindex()


    def change_class_id(self, new_class_id):
        self.metadata.change_class_id(new_class_id)
        # Return the changed resource
        return self.get_resource(self.abspath)


    def reindex(self):
        # Set resource as changed (to reindex resource)
        self.database.change_resource(self)

    #######################################################################
    # Icons
    #######################################################################
    @classmethod
    def get_class_icon(cls, size=16):
        return getattr(cls, 'class_icon%s' % size, None)


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
        return '/ui/ikaaro/icons/%s/%s' % (size, icon)


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


    def get_multilingual_value(self, context, name):
        kw = {}
        languages = context.root.get_value('website_languages')
        for lang in languages:
            kw[lang] = self.get_value(name, language=lang)
        return kw


    json_export_excluded_fields_cls = [
        URI_Field,
        SelectAbspath_Field,
        File_Field,
        Share_Field
    ]

    json_export_excluded_fields_names = [
        "subject",
        "ctime",
        "mtime",
        "uuid",
        "last_author",
        "owner",
        "share",
        "share_exclude",
        "share_interest",
        "share_users",
        "thumbnail",
        "image",
        "status"
    ]

    def get_exportable_fields(self):
        for name, field in self.get_fields():
            if is_prototype(field, tuple(self.json_export_excluded_fields_cls)):
                if is_prototype(field, File_Field):
                    if is_prototype(field.get_widget(field.name), RTEWidget):
                        yield name, field
                continue
            if name in self.json_export_excluded_fields_names:
                continue
            if name.startswith("searchable_"):
                continue
            yield name, field

    def update_metadata_from_dict(self, fields_dict, dry_run=False):
        if dry_run:
            return
        allowed_fields = [name for name, _ in self.get_exportable_fields()]
        for field in fields_dict:
            field_name = field["name"]
            if field_name not in allowed_fields:
                continue
            resource_field = self.get_field(field_name)
            if not resource_field:
                continue
            datatype = resource_field.get_datatype()
            field_value = field["value"]
            is_unicode = is_prototype(datatype, Unicode)
            if not field_value:
                continue
            field_multilingual = field["multilingual"]
            if not field_multilingual:
                if is_unicode:
                    if type(field_value) is list:
                        field_value = [x.decode("utf-8") for x in field_value]
                    else:
                        field_value = field_value.decode("utf-8")
                self.set_value(field_name, field_value)
                continue
            for lang, lang_value in field_value.items():
                if not lang_value:
                    continue
                if is_prototype(datatype, HTMLBody):
                    lang_value = datatype.decode(lang_value)
                if is_unicode:
                    lang_value = lang_value.decode("utf-8")
                self.set_value(field_name, lang_value, language=lang)


    def export_as_json(self, context, only_self=False, exported_fields=None):
        json_namespace = {
            "class_id": getattr(self, "class_id"),
            "class_version": self.class_version,
            "name": self.name,
        }
        fields = []
        for name, field in self.get_exportable_fields():
            datatype = field.get_datatype()
            if exported_fields and name not in exported_fields:
                continue
            field_kw = {
                "name": name,
                "multilingual": field.multilingual
            }
            if not field.multilingual:
                field_kw["value"] = self.get_value(name)
            else:
                field_kw["value"] = self.get_multilingual_value(context, name)
                if is_prototype(datatype, HTMLBody):
                    for k, v in field_kw["value"].items():
                        field_kw["value"][k] = datatype.encode(v)
            fields.append(field_kw)
        json_namespace["fields"] = fields
        return json_namespace



    # Views
    new_instance = AutoAdd(fields=['title', 'location'])
    edit = AutoEdit(fields=['title', 'description', 'subject', 'share'])
    remove = DBResource_Remove()
    get_file = DBResource_GetFile()
    get_image = DBResource_GetImage()
    json_export = AutoJSONResourceExport()
    json_import = AutoJSONResourcesImport()
    # Login/Logout
    login = LoginView()
    logout = LogoutView()
    # Popups
    add_image = DBResource_AddImage()
    add_link = DBResource_AddLink()
    add_media = DBResource_AddMedia()
    # Links
    backlinks = DBResource_Backlinks()
    links = DBResource_Links()


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
register_field('class_version', Date(indexed=True, stored=True))
# Referential integrity
register_field('links', String(multiple=True, indexed=True))
register_field('onchange_reindex', String(multiple=True, indexed=True))
# Full text search
register_field('text', Unicode(indexed=True))
# Time events
register_field('next_time_event', DateTime(stored=True))
register_field('next_time_event_payload', String(stored=True))
