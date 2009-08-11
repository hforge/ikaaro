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

# Import from itools
from itools.core import merge_dicts
from itools.datatypes import String, Tokens
from itools.gettext import MSG
from itools.uri import Path
from itools.stl import set_prefix
from itools.web import INFO, get_context
from itools.xapian import AndQuery, OrQuery, PhraseQuery, NotQuery
from itools.xml import XMLParser

# Import from ikaaro
from ikaaro.buttons import Button, RemoveButton, OrderUpButton
from ikaaro.buttons import OrderDownButton, OrderBottomButton, OrderTopButton
from ikaaro.file import Image
from ikaaro.folder import Folder
from ikaaro.folder_views import Folder_BrowseContent, GoToSpecificDocument
from ikaaro.folder_views import get_workflow_preview
from ikaaro.registry import register_resource_class
from ikaaro.table import OrderedTableFile, OrderedTable
from ikaaro.table_views import OrderedTable_View
from ikaaro.utils import get_base_path_query
from ikaaro.views import CompositeForm
from ikaaro.workflow import WorkflowAware


class AddButton(Button):

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
        prefix  = context.resource.get_pathto(resource)
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
        language = resource.get_content_language(context)
        text = text.get(language, text.keys()[0])
    return text[:text_length] + u"…"



class ResourcesOrderedTable_Ordered(OrderedTable_View):

    title = MSG('Ordered items')

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
        # Remove "sortable" status
        columns = [(name, title, False) for name, title in columns]
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
            if not isinstance(item_resource, WorkflowAware):
                return None
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
    title = MSG('Unordered items')

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
            columns.append(('order_preview', MSG(u"Preview")))
        return columns


    def get_query(self, resource, context):
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


    def get_items(self, resource, context):
        query = self.get_query(resource, context)
        return context.root.search(query)


    def get_item_value(self, resource, context, item, column):
        item_brain, item_resource = item
        if column == 'checkbox':
            return item_brain.name, False
        elif column == 'title':
            return item_resource.get_title(), context.get_link(item_resource)
        elif column == 'path':
            return item_brain.name
        elif column == 'workflow_state':
            # The workflow state
            if not isinstance(item_resource, WorkflowAware):
                return None
            return get_workflow_preview(item_resource, context)
        elif column == 'order_preview':
            return get_resource_preview(item_resource,
                self.preview_image_width, self.preview_image_height,
                self.preview_text_length, context)
        return Folder_BrowseContent.get_item_value(self, resource, context,
                                                   item, column)


    def action_add(self, resource, context, form):
        handler = resource.handler

        order = resource.get_property('order') or []
        if not isinstance(order, list):
            order = list(order)

        index = handler.get_n_records()
        for name in form['ids']:
            handler.add_record({'name': name})
            order.append(str(index))
            index += 1

        resource.set_property('order', order)
        context.message = INFO(u'Resources added to ordered list.')



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
        'name': String(mandatory=True, unique=True, is_indexed=True)}



class ResourcesOrderedTable(OrderedTable):

    class_id = 'resources-ordered-table'
    class_title = MSG(u'Resources Ordered Table')
    class_handler = ResourcesOrderedTableFile
    class_views = ['view', 'last_changes']

    # All types by default
    orderable_classes = ()
    # Every item will be into this resource
    order_root_path = '..'

    # Views
    view = ResourcesOrderedTable_View()


    @classmethod
    def get_metadata_schema(cls):
        return merge_dicts(OrderedTable.get_metadata_schema(),
                           order=Tokens)


    def get_orderable_classes(self):
        return self.orderable_classes


    def get_order_root(self):
        return self.get_resource(self.order_root_path)


    def get_ordered_names(self):
        handler = self.handler
        for record in handler.get_records_in_order():
            yield record.name


    def get_links(self):
        base = self.get_canonical_path()
        handler = self.handler
        links = []

        for record in handler.get_records_in_order():
            # Target resources
            path = handler.get_record_value(record, 'name')
            links.append(str(base.resolve(path)))

        return links


    def update_links(self, old_path, new_path):
        handler = self.handler
        old_name = Path(old_path).get_name()
        new_name = Path(new_path).get_name()
        for record in handler.get_records_in_order():
            name = handler.get_record_value(record, 'name')
            if name == old_name:
                handler.update_record(record.id, **{'name': new_name})

        get_context().server.change_resource(self)



class ResourcesOrderedContainer(Folder):

    class_id = 'resources-ordered-container'
    class_views = Folder.class_views + ['order']

    __fixed_handlers__ = ['order-resources']

    order_path = 'order-resources'
    order_class = ResourcesOrderedTable


    # Views
    order = GoToOrderedTable()


    @staticmethod
    def _make_resource(cls, folder, name, **kw):
        Folder._make_resource(cls, folder, name, **kw)
        # Make the table
        order_class = cls.order_class
        order_class._make_resource(order_class, folder,
                                   '%s/%s' % (name, cls.order_path))


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



register_resource_class(ResourcesOrderedTable)
register_resource_class(ChildrenOrderedTable)
