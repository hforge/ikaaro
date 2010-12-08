# -*- coding: UTF-8 -*-
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
from copy import deepcopy

# Import from itools
from itools.csv import UniqueError
from itools.database import AndQuery, OrQuery, PhraseQuery, NotQuery
from itools.datatypes import String
from itools.gettext import MSG
from itools.handlers.utils import transmap
from itools.stl import set_prefix
from itools.uri import get_reference, resolve_uri2, Path
from itools.web import ERROR, INFO, get_context
from itools.xml import XMLParser

# Import from ikaaro
from ikaaro.buttons import BrowseButton, RemoveButton, OrderUpButton
from ikaaro.buttons import OrderDownButton, OrderBottomButton, OrderTopButton
from ikaaro.file import Image
from ikaaro.folder import Folder
from ikaaro.folder_views import Folder_BrowseContent, GoToSpecificDocument
from ikaaro.table import OrderedTableFile, OrderedTable
from ikaaro.table_views import OrderedTable_View
from ikaaro.utils import get_base_path_query
from ikaaro.views import CompositeForm
from ikaaro.workflow import get_workflow_preview


class AddButton(BrowseButton):

    access = 'is_allowed_to_edit'
    name = 'add'
    title = MSG(u'Add to ordered list')



###########################################################################
# Views
###########################################################################

def get_resource_preview(resource, image_width, image_height, text_length,
                         context):
    # Search for a "order_preview" view
    view = getattr(resource, 'order_preview', None)
    if view is not None:
        prefix = context.resource.get_pathto(resource)
        return set_prefix(view.GET(resource, context), '%s/' % prefix)
    # Render image thumbnail
    if isinstance(resource, Image):
        template = '<img src="%s/;thumb?width=%s&amp;height=%s"/>'
        return XMLParser(template % (
            context.get_link(resource), image_width, image_height))
    # Or textual representation
    try:
        text = resource.to_text()
    except NotImplementedError:
        text = u""
    if isinstance(text, dict):
        language = resource.get_edit_languages(context)[0]
        text = text.get(language, text.keys()[0])
    return text[:text_length] + u"…"



class ResourcesOrderedTable_Ordered(OrderedTable_View):

    title = MSG(u'Ordered items')

    order_preview = True
    preview_image_width = 64
    preview_image_height = 64
    preview_text_length = 100

    table_actions = [RemoveButton(confirm=None,
                                  title=MSG(u"Remove from ordered list")),
                     OrderUpButton, OrderDownButton, OrderTopButton,
                     OrderBottomButton]


    def get_table_columns(self, resource, context):
        columns = OrderedTable_View.get_table_columns(self, resource,
                                                      context)
        # Remove column with id and replace it by title,
        # and add a column for the workflow state
        columns[1] = ('title', MSG(u'Title'), False)
        columns.append(('workflow_state', MSG(u'State'), False))
        if self.order_preview:
            columns.append(('order_preview', MSG(u"Preview"), False))
        return columns


    def get_item_value(self, resource, context, item, column):
        order_root = resource.get_order_root()
        try:
            item_resource = order_root.get_resource(item.name)
        except LookupError:
            item_resource = None

        if column == 'title':
            if item_resource:
                title = item_resource.get_title()
                return title, context.get_link(item_resource)
            # Miss
            return item.name
        elif column == 'workflow_state':
            # The workflow state
            if item_resource is None:
                # Miss
                label = MSG(u'Broken').gettext().encode('utf-8')
                state = '<strong class="broken">%s</strong>' % label
                return XMLParser(state)
            return get_workflow_preview(item_resource, context)
        elif column == 'order_preview':
            if item_resource is None:
                return None
            return get_resource_preview(item_resource,
                    self.preview_image_width, self.preview_image_height,
                    self.preview_text_length, context)
        return OrderedTable_View.get_item_value(self, resource, context,
                                                item, column)


    def sort_and_batch(self, resource, context, items):
        # Preserve the order
        return items




class ResourcesOrderedTable_Unordered(Folder_BrowseContent):

    access = 'is_allowed_to_edit'
    title = MSG(u'Unordered items')

    order_preview = True
    preview_image_width = 64
    preview_image_height = 64
    preview_text_length = 100

    table_actions = [AddButton]

    # Reset unrequired stuff
    context_menus = []
    search_template = None
    search_schema = {}
    def get_search_namespace(self, resource, context):
        return {}
    def get_query_schema(self):
        return {}


    def get_table_columns(self, resource, context):
        columns = [('checkbox', None),
                   ('title', MSG(u'Title')),
                   ('path', MSG(u'Path')),
                   ('workflow_state', MSG(u'State'))]
        if self.order_preview:
            columns.append(('order_preview', MSG(u"Preview"), False))
        return columns


    def get_items_query(self, resource, context):
        # Only in the given root
        parent_path = resource.get_order_root().get_canonical_path()
        query_base_path = get_base_path_query(str(parent_path))
        # Only the given types
        query_formats = [PhraseQuery('format', cls.class_id)
                         for cls in resource.get_orderable_classes()]
        query_formats = OrQuery(*query_formats)
        query_excluded = [NotQuery(PhraseQuery('name', name))
                          for name in resource.get_ordered_names()]
        return AndQuery(query_base_path, query_formats, *query_excluded)


    def get_key_sorted_by_title(self):
        # As we do not show abspath, title must return a value
        # to avoid problem when sorting on title
        def key(item):
            title = item.title or unicode(item.name)
            return title.lower().translate(transmap)
        return key


    def get_items(self, resource, context):
        query = self.get_items_query(resource, context)
        return context.root.search(query)


    def get_item_value(self, resource, context, item, column):
        item_brain, item_resource = item
        if column == 'checkbox':
            return item_brain.name, False
        elif column == 'title':
            # As we do not show abspath, title must return a value
            title = item_brain.title or unicode(item_brain.name)
            return title, context.get_link(item_resource)
        elif column == 'path':
            return item_brain.name
        elif column == 'workflow_state':
            # The workflow state
            return get_workflow_preview(item_resource, context)
        elif column == 'order_preview':
            return get_resource_preview(item_resource,
                self.preview_image_width, self.preview_image_height,
                self.preview_text_length, context)
        return Folder_BrowseContent.get_item_value(self, resource, context,
                                                   item, column)


    def action_add(self, resource, context, form):
        handler = resource.handler
        added = []
        not_added = []
        for name in form['ids']:
            try:
                handler.add_record({'name': name})
                added.append(name)
            except UniqueError:
                not_added.append(name)

        message = []
        if added:
            resources = ', '.join(added)
            msg = INFO(u'Resources added to ordered list: {resources}.')
            msg = msg(resources=resources)
            message.append(msg)
            # Reindex
            context.database.change_resource(resource)
        if not_added:
            resources = ', '.join(not_added)
            msg = ERROR(u'Resources already in the ordered list: {resources}.')
            msg = msg(resources=resources)
            message.append(msg)

        context.message = message



class ResourcesOrderedTable_View(CompositeForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'View')
    template = '/ui/future/order_view.xml'

    subviews = [ResourcesOrderedTable_Ordered(),
                ResourcesOrderedTable_Unordered()]


    def get_namespace(self, resource, context):
        views = []
        for view in self.subviews:
            views.append({'title': view.title,
                          'view': view.GET(resource, context)})
        return {'views': views}



class GoToOrderedTable(GoToSpecificDocument):

    access = 'is_allowed_to_edit'
    title = MSG(u'Order resources')


    def get_specific_document(self, resource, context):
        return resource.order_path



class GoToFirstOrderedResource(GoToSpecificDocument):

    access = 'is_allowed_to_view'
    title = MSG(u'View')


    def GET(self, resource, context):
        specific_document = self.get_specific_document(resource, context)
        if specific_document is None:
            # XXX White page
            return ''
        return GoToSpecificDocument.GET(self, resource, context)


    def get_specific_document(self, resource, context):
        # TODO ACL?
        names = list(resource.get_ordered_names())
        if names:
            return names[0]
        return None



###########################################################################
# Resources
###########################################################################

class ResourcesOrderedTableFile(OrderedTableFile):

    record_properties = {
        'name': String(mandatory=True, unique=True, indexed=True)}



class ResourcesOrderedTable(OrderedTable):

    class_id = 'resources-ordered-table'
    class_title = MSG(u'Resources Ordered Table')
    class_handler = ResourcesOrderedTableFile
    class_views = ['view', 'commit_log']

    # All types by default
    orderable_classes = ()
    # Every item will be into this resource
    order_root_path = '..'

    # Views
    view = ResourcesOrderedTable_View()


    def get_orderable_classes(self):
        return self.orderable_classes


    def get_order_root(self):
        return self.get_resource(self.order_root_path)


    def get_ordered_names(self):
        handler = self.handler
        for record in handler.get_records_in_order():
            yield handler.get_record_value(record, 'name')


    def get_links(self):
        base = self.get_order_root().get_canonical_path()
        return set([
            str(resolve_uri2(base, name))
            for name in self.get_ordered_names() ])


    def update_links(self, source, target):
        base = self.get_order_root().get_canonical_path()
        handler = self.handler

        for record in handler.get_records_in_order():
            name = handler.get_record_value(record, 'name')
            path = str(resolve_uri2(base, name))
            if path == source:
                new_path = str(base.get_pathto(target))
                # Check if the new path is inside the order root
                # otherwise delete the record
                new_abs_path = base.resolve2(new_path)
                if base.get_prefix(new_abs_path) != base:
                    # delete the record
                    handler.del_record(record.id)
                else:
                    handler.update_record(record.id, **{'name': new_path})
        get_context().database.change_resource(self)


    def update_relative_links(self, source):
        """Links are relative to order root"""
        order_root_source = resolve_uri2(source, self.order_root_path)
        order_root_source = Path(order_root_source)
        order_root_target = self.get_order_root().get_canonical_path()
        resources_old2new = get_context().database.resources_old2new
        new_order_root_target = resources_old2new.get(order_root_target,
                                                      order_root_target)

        handler = self.handler
        get_value = handler.get_record_value
        for record in handler.get_records():
            path = get_value(record, 'name')
            if not path:
                continue
            ref = get_reference(str(path))
            if ref.scheme:
                continue
            path = ref.path
            # Calcul the old absolute path
            old_abs_path = order_root_source.resolve2(path)
            # Check if the target path has not been moved
            new_abs_path = resources_old2new.get(old_abs_path,
                                                 old_abs_path)
            # Build the new reference with the right path
            # Absolute path allow to call get_pathto with the target
            new_ref = deepcopy(ref)
            new_ref.path = str(new_order_root_target.get_pathto(new_abs_path))
            # Update the record
            handler.update_record(record.id, **{'name': str(new_ref)})



class ResourcesOrderedContainer(Folder):

    class_id = 'resources-ordered-container'
    class_views = Folder.class_views + ['order']

    __fixed_handlers__ = ['order-resources']

    order_path = 'order-resources'
    order_class = ResourcesOrderedTable


    # Views
    order = GoToOrderedTable()


    def init_resource(self, **kw):
        self.make_resource(self.order_path, self.order_class)


    def get_ordered_names(self, context=None):
        order_table = self.get_resource(self.order_path)
        if context is None:
            for name in order_table.get_ordered_names():
                yield name
            return
        # Apply ACL
        order_root = order_table.get_order_root()
        for name in order_table.get_ordered_names():
            resource = order_root.get_resource(name)
            ac = resource.get_access_control()
            if ac.is_allowed_to_view(context.user, resource):
                yield name



###########################################################################
# XXX migrate to "resource-ordered-table" in your project
# TODO remove in 0.70
###########################################################################

class ChildrenOrderedTable(ResourcesOrderedTable):

    class_id = 'children-ordered-table'

