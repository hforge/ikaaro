# -*- coding: UTF-8 -*-
# Copyright (C) 2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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

# Import from the Python Image Library
try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

# Import from itools
from itools.core import merge_dicts
from itools.database import AndQuery, NotQuery, PhraseQuery, OrQuery, TextQuery
from itools.datatypes import Boolean, Enumerate, Integer, String, Unicode
from itools.gettext import MSG
from itools.handlers import checkid
from itools.handlers.utils import transmap
from itools.html import stream_is_empty
from itools.uri import get_reference, Path
from itools.web import BaseView, STLView, get_context

# Import from ikaaro
from autoform import SelectWidget, TextWidget
from buttons import PasteButton
from buttons import Remove_BrowseButton, RenameButton, CopyButton, CutButton
from buttons import ZipButton
from datatypes import CopyCookie
from exceptions import ConsistencyError
from utils import generate_name, get_base_path_query, get_content_containers
from views import IconsView, BrowseForm, ContextMenu
import messages


class SearchTypes_Enumerate(Enumerate):

    def get_options(self):
        context = get_context()
        resource = context.resource
        view = context.view
        # 1. Build the query of all objects to search
        query = get_base_path_query(resource.abspath)
        if view.search_content_only(resource, context) is True:
            content_query = PhraseQuery('is_content', True)
            query = AndQuery(query, content_query)

        # 2. Compute children_formats
        children_formats = set()
        for child in context.search(query).get_documents():
            children_formats.add(child.format)

        # 3. Do not show two options with the same title
        formats = {}
        for type in children_formats:
            cls = context.database.get_resource_class(type)
            title = cls.class_title.gettext()
            formats.setdefault(title, []).append(type)

        # 4. Build the namespace
        types = []
        for title, type in formats.items():
            type = ','.join(type)
            types.append({'name': type, 'value': title})
        types.sort(key=lambda x: x['value'].lower())

        return types


    # This is done to fix an error: select one resource type, remove all
    # resources, then traceback.
    def is_valid(self, value):
        return True



class ZoomMenu(ContextMenu):

    title = MSG(u'Zoom')

    def get_items(self):
        uri = self.context.uri

        # Compute previous and next sizes
        current_size = self.context.query['size']
        size_steps = self.resource.SIZE_STEPS
        min_size = size_steps[0]
        max_size = size_steps[-1]
        current_size = max(min_size, min(current_size, max_size))
        previous_size = min_size
        next_size = max_size
        for step in size_steps:
            if step < current_size:
                previous_size = step
            if next_size is max_size and step > current_size:
                next_size = step

        next_size = str(next_size)
        previous_size = str(previous_size)
        return [
            {'title': MSG(u'Zoom In'),
             'src': '/ui/icons/16x16/zoom_in.png',
             'href': uri.replace(size=next_size)},
            {'title': MSG(u'Zoom Out'),
             'src': '/ui/icons/16x16/zoom_out.png',
             'href': uri.replace(size=previous_size)}
        ]



class Folder_View(BaseView):

    access = 'is_allowed_to_view_folder'
    title = MSG(u'View')


    def GET(self, resource, context):
        stream = resource.get_html_field_body_stream('index')
        stream = list(stream)
        return stream if not stream_is_empty(stream) else ''



class Folder_NewResource(IconsView):

    access = 'is_allowed_to_add'
    title = MSG(u'Add resource')
    icon = 'new.png'


    def GET(self, resource, context):
        # If only one type of event, we redirect on it
        items = self.get_items(resource, context)
        if len(items) == 1:
            return self.get_url(items[0].class_id, context)

        return super(Folder_NewResource, self).GET(resource, context)


    def get_url(self, class_id, context):
        query = context.uri.query.copy()
        query['type'] = class_id
        query['referrer'] = context.get_referrer()
        uri = context.uri.resolve('./;new_resource')
        uri.query = query
        return uri


    def get_items(self, resource, context):
        # 1. Static classes
        aux = set()
        document_types = []
        for container in get_content_containers(context):
            if container.class_id in aux:
                continue
            aux.add(container.class_id)
            for cls in container.get_document_types():
                if cls not in document_types:
                    document_types.append(cls)

        # 2. Add dynamic models
        for cls in context.database.get_dynamic_classes():
            document_types.append(cls)

        # Ok
        return document_types


    def get_namespace(self, resource, context):
        items = [
            {'icon': '/ui/' + cls.class_icon48,
             'title': cls.class_title,
             'description': cls.class_description,
             'url': self.get_url(cls.class_id, context)}
            for cls in self.get_items(resource, context) ]

        return {'batch': None, 'items': items}



class Folder_Rename(STLView):

    access = 'is_allowed_to_edit'
    title = MSG(u'Rename resources')
    template = '/ui/folder/rename.xml'
    query_schema = {
        'ids': String(multiple=True)}
    schema = {
        'paths': String(multiple=True, mandatory=True),
        'new_names': String(multiple=True, mandatory=True)}
    goto_after = ';browse_content'


    def get_namespace(self, resource, context):
        ids = context.query['ids']
        # Filter names which the authenticated user is not allowed to move
        root = context.root
        user = context.user
        paths = [ x for x in ids
                  if root.is_allowed_to_move(user, resource.get_resource(x)) ]

        # Build the namespace
        paths.sort()
        paths.reverse()
        items = []
        for path in paths:
            if '/' in path:
                parent_path, name = path.rsplit('/', 1)
                parent_path += '/'
            else:
                parent_path = ''
                name = path
            items.append({
                'path': path,
                'parent_path': parent_path,
                'name': name})

        return {'items': items}


    def action(self, resource, context, form):
        paths = form['paths']
        new_names = form['new_names']

        paths.sort()
        paths.reverse()
        # Clean the copy cookie if needed
        cut, cp_paths = context.get_cookie('ikaaro_cp', datatype=CopyCookie)

        renamed = []
        referenced = []
        # Process input data
        abspath = resource.abspath
        for i, path in enumerate(paths):
            new_name = new_names[i]
            new_name = checkid(new_name)
            if new_name is None:
                context.message = messages.MSG_BAD_NAME
                return
            # Split the path
            if '/' in path:
                parent_path, old_name = path.rsplit('/', 1)
                container = resource.get_resource(parent_path)
            else:
                old_name = path
                container = resource
            # Check the name really changed
            if new_name == old_name:
                continue
            # Check there is not another resource with the same name
            if container.get_resource(new_name, soft=True) is not None:
                context.message = messages.MSG_EXISTANT_FILENAME
                return
            # Clean cookie (FIXME Do not clean the cookie, update it)
            if cp_paths and str(abspath.resolve2(path)) in cp_paths:
                context.del_cookie('ikaaro_cp')
                cp_paths = []
            # Rename
            try:
                container.move_resource(old_name, new_name)
            except ConsistencyError:
                referenced.append(old_name)
                continue
            else:
                renamed.append(old_name)

        if referenced and not renamed:
            resources = ', '.join(referenced)
            message = messages.MSG_RESOURCES_REFERENCED(resources=resources)
        else:
            message = messages.MSG_RENAMED
        return context.come_back(message, goto=self.goto_after)



class Folder_BrowseContent(BrowseForm):

    access = 'is_allowed_to_view'
    title = MSG(u'Browse Content')
    context_menus = []
    query_schema = merge_dicts(BrowseForm.query_schema,
        sort_by=String(default='mtime'),
        reverse=Boolean(default=True))
    schema = {
        'ids': String(multiple=True, mandatory=True)}

    # Search Form
    search_widgets = [
        TextWidget('text', title=MSG(u'Text')),
        SelectWidget('format', title=MSG(u'Type'))]
    search_schema = {
        'text': Unicode,
        'format': SearchTypes_Enumerate}

    # Table
    table_columns = [
        ('checkbox', None),
        ('icon', None),
        ('abspath', MSG(u'Path')),
        ('title', MSG(u'Title')),
        ('format', MSG(u'Type')),
        ('mtime', MSG(u'Last Modified')),
        ('last_author', MSG(u'Last Author'))]
    table_actions = [
        Remove_BrowseButton, RenameButton,
        CopyButton, CutButton, PasteButton,
        ZipButton]


    def search_content_only(self, resource, context):
        return resource.is_content


    def get_scripts(self, context):
        scripts = []
        if self.search_widgets:
            for widget in self.search_widgets:
                for script in widget.scripts:
                    if script not in scripts:
                        scripts.append(script)

        return scripts


    def get_styles(self, context):
        styles = []
        if self.search_widgets:
            for widget in self.search_widgets:
                for style in widget.styles:
                    if style not in styles:
                        styles.append(style)
        return styles


    depth = None
    base_classes = None
    def get_items_query(self, resource, context):
        # Search in subtree
        query = get_base_path_query(resource.abspath, max_depth=self.depth)

        # Base classes
        base_classes = self.base_classes
        if base_classes is not None:
            base_classes_query = OrQuery(*
                [ PhraseQuery('base_classes', x) for x in base_classes ])
            query = AndQuery(query, base_classes_query)

        # Exclude non-content
        if self.search_content_only(resource, context) is True:
            query = AndQuery(query, PhraseQuery('is_content', True))

        return query


    def get_search_query(self, resource, context):
        query = AndQuery()
        form = context.query
        for key, datatype in self.search_schema.items():
            value = form[key]
            if value is None or value == '':
                continue
            # Special case: search on text, title and name AS AndQuery
            if key == 'text':
                text_query = []
                value = value.split(' ')
                for v in value:
                    t_query = OrQuery(TextQuery('title', v),
                                      TextQuery('text', v),
                                      PhraseQuery('name', v))
                    text_query.append(t_query)
                if len(text_query) == 1:
                    text_query = text_query[0]
                else:
                    text_query = AndQuery(*text_query)
                query.append(text_query)
            # Special case: type
            elif key == 'format':
                squery = [ PhraseQuery('format', x) for x in value.split(',') ]
                squery = squery[0] if len(squery) == 1 else OrQuery(*squery)
                query.append(squery)
            # Multiple
            elif datatype.multiple is True:
                query.append(OrQuery(*[ PhraseQuery(key, x) for x in value ]))
            # Singleton
            else:
                if value is False:
                    # FIXME No value means False in xapian
                    query.append(NotQuery(PhraseQuery(key, True)))
                else:
                    query.append(PhraseQuery(key, value))
        return query


    def get_items(self, resource, context):
        # Base query
        query = self.get_items_query(resource, context)

        # Search form
        search_query = self.get_search_query(resource, context)
        if search_query:
            query = AndQuery(query, search_query)

        # Search
        return context.search(query)


    def _get_key_sorted_by_unicode(self, field):
        def key(item):
            return getattr(item, field).lower().translate(transmap)
        return key


    def _get_key_sorted_by_user(self, field):
        get_user_title = self.context.root.get_user_title
        def key(item, cache={}):
            user = getattr(item, field)
            if user in cache:
                return cache[user]
            if user:
                title = get_user_title(user)
                value = title.lower().translate(transmap)
            else:
                value = None
            cache[user] = value
            return value
        return key


    def get_key_sorted_by_title(self):
        return self._get_key_sorted_by_unicode('title')


    def get_key_sorted_by_format(self):
        database = self.context.database
        def key(item, cache={}):
            format = item.format
            if format in cache:
                return cache[format]
            cls = database.get_resource_class(format)
            value = cls.class_title.gettext().lower().translate(transmap)
            cache[format] = value
            return value
        return key


    def get_key_sorted_by_last_author(self):
        return self._get_key_sorted_by_user('last_author')


    def sort_and_batch(self, resource, context, results):
        start = context.query['batch_start']
        size = context.query['batch_size']
        sort_by = context.query['sort_by']
        reverse = context.query['reverse']

        if sort_by is None:
            get_key = None
        else:
            get_key = getattr(self, 'get_key_sorted_by_' + sort_by, None)

        # Case 1: Custom but slower sort algorithm
        if get_key:
            items = results.get_documents()
            items.sort(key=get_key(), reverse=reverse)
            if size:
                items = items[start:start+size]
            elif start:
                items = items[start:]
            database = resource.database
            return [ database.get_resource(x.abspath) for x in items ]

        # Case 2: Faster Xapian sort algorithm
        items = results.get_resources(sort_by, reverse, start, size)
        return list(items)


    def get_item_value(self, resource, context, item, column):
        if column == 'checkbox':
            # checkbox
            parent = item.parent
            if parent is None:
                return None
            if item.name in parent.__fixed_handlers__:
                return None
            id = resource.abspath.get_pathto(item.abspath)
            id = str(id)
            return id, False
        elif column == 'icon':
            # icon
            path_to_icon = item.get_resource_icon(16)
            if not path_to_icon:
                return None
            if path_to_icon.startswith(';'):
                path_to_icon = Path('%s/' % item.name).resolve(path_to_icon)
            return path_to_icon
        elif column == 'abspath':
            # Name
            id = resource.abspath.get_pathto(item.abspath)
            id = str(id)
            view = item.get_view(None)
            if view is None:
                return id
            href = '%s/' % context.get_link(item)
            return id, href
        elif column == 'format':
            # Type
            return item.class_title.gettext()
        elif column == 'mtime':
            # Last Modified
            mtime = item.get_value('mtime')
            if mtime:
                return context.format_datetime(mtime)
            return None
        elif column == 'last_author':
            # Last author
            author =  item.get_value('last_author')
            return context.root.get_user_title(author) if author else None
        elif column == 'row_css':
            return None

        # Default
        return item.get_value_title(column)


    #######################################################################
    # Form Actions
    #######################################################################
    def action_remove(self, resource, context, form):
        ids = form['ids']

        # Remove resources
        removed = []
        referenced = []
        not_removed = []
        user = context.user
        root = context.root

        # We sort and reverse ids in order to
        # remove the childs then their parents
        ids.sort()
        ids.reverse()
        for name in ids:
            child = resource.get_resource(name)
            if root.is_allowed_to_remove(user, child):
                # Remove resource
                try:
                    resource.del_resource(name)
                except ConsistencyError:
                    referenced.append(name)
                    continue
                removed.append(name)
            else:
                not_removed.append(name)

        message = []
        if removed:
            resources = ', '.join(removed)
            msg = messages.MSG_RESOURCES_REMOVED(resources=resources)
            message.append(msg)
        if referenced:
            items = []
            for name in referenced:
                item = resource.get_resource(name)
                view = item.get_view('backlinks')
                if context.is_access_allowed(item, view):
                    items.append({'title': item.get_title(),
                                  'href': '%s/;backlinks' % item.abspath})
            msg = messages.MSG_RESOURCES_REFERENCED_HTML(resources=items)
            message.append(msg)
        if not_removed:
            resources = ', '.join(not_removed)
            msg = messages.MSG_RESOURCES_NOT_REMOVED(resources=resources)
            message.append(msg)
        if not removed and not referenced and not not_removed:
            message.append(messages.MSG_NONE_REMOVED)
        context.message = message


    def action_rename(self, resource, context, form):
        ids = form['ids']
        # Filter names which the authenticated user is not allowed to move
        root = context.root
        user = context.user
        paths = [ x for x in ids
                  if root.is_allowed_to_move(user, resource.get_resource(x)) ]

        # Check input data
        if not paths:
            context.message = messages.MSG_NONE_SELECTED
            return

        # FIXME Hack to get rename working. The current user interface forces
        # the rename_form to be called as a form action, hence with the POST
        # method, but it should be a GET method. Maybe it will be solved after
        # the needed folder browse overhaul.
        ids_list = '&'.join([ 'ids=%s' % x for x in paths ])
        uri = '%s/;rename?%s' % (context.get_link(resource), ids_list)
        return get_reference(uri)


    def action_copy(self, resource, context, form):
        ids = form['ids']
        # Filter names which the authenticated user is not allowed to copy
        root = context.root
        user = context.user
        names = [ x for x in ids
                  if root.is_allowed_to_copy(user, resource.get_resource(x)) ]

        # Check input data
        if not names:
            context.message = messages.MSG_NONE_SELECTED
            return

        abspath = resource.abspath
        cp = (False, [ str(abspath.resolve2(x)) for x in names ])
        cp = CopyCookie.encode(cp)
        context.set_cookie('ikaaro_cp', cp, path='/')
        # Ok
        context.message = messages.MSG_COPIED


    def action_cut(self, resource, context, form):
        ids = form['ids']
        # Filter names which the authenticated user is not allowed to move
        root = context.root
        user = context.user
        names = [ x for x in ids
                  if root.is_allowed_to_move(user, resource.get_resource(x)) ]

        # Check input data
        if not names:
            context.message = messages.MSG_NONE_SELECTED
            return

        abspath = resource.abspath
        cp = (True, [ str(abspath.resolve2(x)) for x in names ])
        cp = CopyCookie.encode(cp)
        context.set_cookie('ikaaro_cp', cp, path='/')

        context.message = messages.MSG_CUT


    action_paste_schema = {}
    def action_paste(self, resource, context, form):
        # Check there is something to paste
        cut, paths = context.get_cookie('ikaaro_cp', datatype=CopyCookie)
        if len(paths) == 0:
            context.message = messages.MSG_NO_PASTE
            return

        # Paste
        target = resource
        pasted = []
        not_allowed = []
        for path in paths:
            # Check the source resource still exists
            source = target.get_resource(path, soft=True)
            if source is None:
                continue

            # If cut&paste in the same place, do nothing
            if cut is True:
                if target == source.parent:
                    pasted.append(source.name)
                    continue

            name = generate_name(source.name, target.get_names(), '_copy_')
            if cut is True:
                # Cut&Paste
                try:
                    target.move_resource(path, name)
                except ConsistencyError:
                    not_allowed.append(source.name)
                    continue
                else:
                    pasted.append(name)
            else:
                # Copy&Paste
                try:
                    target.copy_resource(path, name)
                except ConsistencyError:
                    not_allowed.append(source.name)
                    continue
                else:
                    pasted.append(name)

        # Cut, clean cookie
        if cut is True:
            context.del_cookie('ikaaro_cp')

        message = []
        if pasted:
            resources = ', '.join(pasted)
            message.append(messages.MSG_RESOURCES_PASTED(resources=resources))
        if not_allowed:
            resources = ', '.join(not_allowed)
            msg = messages.MSG_RESOURCES_NOT_PASTED(resources=resources)
            message.append(msg)

        context.message = message


    def action_zip(self, resource, context, form):
        names = sorted(form['ids'], reverse=True)
        data = resource.export_zip(names)
        # Content-Type & Content-Disposition
        context.set_content_type('application/zip')
        filename = 'archive.zip'
        context.set_content_disposition('inline', filename)
        # Ok
        return data



class Folder_PreviewContent(Folder_BrowseContent):

    title = MSG(u'Preview Content')
    styles = ['/ui/gallery/style.css']

    context_menus = Folder_BrowseContent.context_menus + [ZoomMenu()]


    base_classes = ('image',)


    def get_query_schema(self):
        # Define a huge batch limit, and the image size parameter
        schema = super(Folder_PreviewContent, self).get_query_schema()
        return merge_dicts(schema,
                           batch_size=Integer(default=0),
                           size=Integer(default=128),
                           width=String,
                           height=String)


    # Table
    table_template = '/ui/folder/browse_image.xml'

    def get_table_head(self, resource, context, items):
        actions = self.actions_namespace

        # Get from the query
        query = context.query
        sort_by = query['sort_by']
        reverse = query['reverse']

        columns = self._get_table_columns(resource, context)
        columns_ns = []
        for name, title, sortable, css in columns:
            if name == 'checkbox':
                # Type: checkbox
                if  actions:
                    columns_ns.append({'is_checkbox': True})
            elif title is None:
                # Type: nothing
                continue
            elif not sortable:
                # Type: nothing or not sortable
                columns_ns.append({
                    'is_checkbox': False,
                    'title': title,
                    'href': None})
            else:
                # Type: normal
                kw = {'sort_by': name}
                if name == sort_by:
                    col_reverse = (not reverse)
                    order = 'up' if reverse else 'down'
                else:
                    col_reverse = False
                    order = 'none'
                kw['reverse'] = Boolean.encode(col_reverse)
                columns_ns.append({
                    'is_checkbox': False,
                    'title': title,
                    'order': order,
                    'href': context.uri.replace(**kw),
                    })


    def get_table_namespace(self, resource, context, items):
        # Get from the query
        query = context.query
        width = query['width']
        height = query['height']

        # (0) Zoom
        current_size = query['size']
        min_size = resource.SIZE_STEPS[0]
        max_size = resource.SIZE_STEPS[-1]
        current_size = max(min_size, min(current_size, max_size))

        # (1) Actions (submit buttons)
        self._items = items
        actions = self.actions_namespace

        # (2) Table Head: columns
        table_head = self.get_table_head(resource, context, items)

        # (3) Table Body: rows
        columns = self._get_table_columns(resource, context)
        rows = []
        for item in items:
            row = {'checkbox': False,
                   # These are required for internal use
                   'title_or_name': item.get_title()}
            # XXX Already hard-coded in the catalog search
            row['is_folder'] = (item.class_id == 'folder')
            for name, title, sortable, css in columns:
                value = self.get_item_value(resource, context, item, name)
                if value is None:
                    continue
                elif name == 'checkbox':
                    if actions:
                        value, checked = value
                        row['checkbox'] = True
                        row['id'] = value
                        row['checked'] = checked
                elif name == 'abspath':
                    if type(value) is tuple:
                        row['name'], row['href'] = value
                    else:
                        row['name'] = value
                        row['href'] = None
                else:
                    row[name] = value
            rows.append(row)

        return {
            'root': resource.parent is None,
            'size': current_size,
            'width': width,
            'height': height,
            'css': self.table_css,
            'columns': table_head,
            'rows': rows,
            'actions': actions}



class Folder_Thumbnail(BaseView):

    access = True

    default_icon = '/ui/gallery/folder.png'

    def GET(self, resource, context):
        default_icon = resource.get_resource(self.default_icon)
        if PILImage is None:
            # Full size but better than nothing
            data = default_icon.to_str()
            format = 'png'
        else:
            # Default icon for empty or inaccessible folders
            width = context.get_form_value('width', type=Integer, default=48)
            height = context.get_form_value('height', type=Integer, default=48)
            data, format = default_icon.get_thumbnail(width, height)

        # XXX Don't cache nothing here
        # The image thumbnail was cached in the image handler
        # The folder thumbnail was cached in the folder handler
        # Accessible images depend on too many parameters

        context.content_type = 'image/%s' % format
        return data



class GoToSpecificDocument(BaseView):

    access = 'is_allowed_to_view'
    title = MSG(u'Front Page')
    icon = 'view.png'
    specific_document = 'FrontPage'
    specific_view = None


    def get_specific_document(self, resource, context):
        return self.specific_document


    def get_specific_view(self, resource, context):
        return self.specific_view


    def GET(self, resource, context):
        specific_document = self.get_specific_document(resource, context)
        specific_view = self.get_specific_view(resource, context)
        goto = '%s/%s' % (context.get_link(resource), specific_document)
        if specific_view:
            goto = '%s/;%s' % (goto, specific_view)
        goto = get_reference(goto)

        # Keep the message
        message = context.get_form_value('message')
        if message:
            goto = goto.replace(message=message)

        return goto
