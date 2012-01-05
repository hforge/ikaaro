# -*- coding: UTF-8 -*-
# Copyright (C) 2011 Sylvain Taverne <sylvain@itaapy.com>
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
from itools.database import PhraseQuery
from itools.gettext import MSG
from itools.web import INFO, get_context

# Import from ikaaro
from buttons import BrowseButton
from fields import URI_Field
from folder import Folder
from folder_views import Folder_BrowseContent



class OrderUpButton(BrowseButton):

    access = 'is_allowed_to_edit'
    name = 'order_up'
    title = MSG(u'Order up')



class OrderDownButton(BrowseButton):

    access = 'is_allowed_to_edit'
    name = 'order_down'
    title = MSG(u'Order down')



class OrderTopButton(BrowseButton):

    access = 'is_allowed_to_edit'
    name = 'order_top'
    title = MSG(u'Order top')



class OrderBottomButton(BrowseButton):

    access = 'is_allowed_to_edit'
    name = 'order_bottom'
    title = MSG(u'Order bottom')


class OrderButton(BrowseButton):

    access = 'is_allowed_to_edit'
    name = 'add_to_ordered'
    title = MSG(u'Add to ordered list')


class UnOrderButton(BrowseButton):

    access = 'is_allowed_to_edit'
    name = 'remove_from_ordered'
    title = MSG(u'Remove from ordered list')




class OrderedFolder_BrowseContent(Folder_BrowseContent):

    query_schema = Folder_BrowseContent.query_schema.copy()
    query_schema['sort_by'] = query_schema['sort_by'](default='order')
    query_schema['reverse'] = query_schema['reverse'](default=False)

    table_columns = (Folder_BrowseContent.table_columns +
                     [('order', MSG(u'Order'))])

    def get_table_actions(self, resource, context):
        proxy = super(OrderedFolder_BrowseContent, self)
        buttons = proxy.get_table_actions(resource, context)

        buttons = list(buttons)
        buttons += [OrderUpButton, OrderDownButton, OrderTopButton,
                    OrderBottomButton]
        if resource.allow_to_unorder_items:
            buttons += [OrderButton, UnOrderButton]

        return buttons


    def get_search_query(self, resource, context):
        proxy = super(OrderedFolder_BrowseContent, self)
        query = proxy.get_search_query(resource, context)
        if resource.base_classes:
            query.append(PhraseQuery('base_classes', resource.base_classes))
        return query


    def get_key_sorted_by_order(self):
        context = get_context()
        ordered_names = list(context.resource.get_ordered_values())
        nb_ordered_names = len(ordered_names)
        def key(item):
            try:
                return ordered_names.index(item.name)
            except ValueError:
                return nb_ordered_names

        return key


    def get_item_value(self, resource, context, item, column):
        if column == 'order':
            ordered_ids = list(resource.get_ordered_values())
            if item.name in ordered_ids:
                return ordered_ids.index(item.name) + 1
            return MSG(u'Not ordered')

        proxy = super(OrderedFolder_BrowseContent, self)
        return proxy.get_item_value(resource, context, item, column)


    ######################################################################
    # Actions
    ######################################################################
    def action_remove(self, resource, context, form):
        # Remove from ordered list
        resource.order_remove(form['ids'])
        # Super
        proxy = super(OrderedFolder_BrowseContent, self)
        return proxy.action_remove(resource, context, form)


    def action_order_up(self, resource, context, form):
        ids = form['ids']
        resource.order_up(ids)
        context.message = INFO(u'Resources ordered up.')


    def action_order_down(self, resource, context, form):
        ids = form['ids']
        resource.order_down(ids)
        context.message = INFO(u'Resources ordered down.')


    def action_order_top(self, resource, context, form):
        ids = form['ids']
        resource.order_top(ids)
        context.message = INFO(u'Resources ordered on top.')


    def action_order_bottom(self, resource, context, form):
        ids = form['ids']
        resource.order_bottom(ids)
        context.message = INFO(u'Resources ordered on bottom.')


    def action_add_to_ordered(self, resource, context, form):
        ids = form['ids']
        resource.order_add(ids)
        context.message = INFO(u'Resources ordered on bottom.')


    def action_remove_from_ordered(self, resource, context, form):
        ids = form['ids']
        resource.order_remove(ids)
        context.message = INFO(u'Resources unordered.')



###############################################
# OrderAware
###############################################

class OrderedFolder(Folder):

    class_title = MSG(u'Ordered Folder')
    class_views = ['browse_content']

    # Fields
    order = URI_Field(title=MSG(u'Order'), multiple=True)

    allow_to_unorder_items = False


    def make_resource(self, name, cls, **kw):
        resource = super(OrderedFolder, self).make_resource(name, cls, **kw)
        if self.can_be_ordered(cls):
            order = self.get_value('order')
            order = order + [resource.name]
            self.set_value('order', order)
        return resource


    base_classes = None
    def can_be_ordered(self, cls):
        if not self.base_classes:
            return True
        for base_class in cls.__mro__:
            if getattr(base_class, 'class_id', None) in self.base_classes:
                return True
        return False



    def get_ordered_values(self):
        ordered_names = list(self.get_value('order'))
        # Unordered names
        if self.allow_to_unorder_items is False:
            for name in self.get_names():
                if name not in ordered_names:
                    ordered_names.append(name)
        return ordered_names


    def get_resources_in_order(self):
        for name in self.get_ordered_values():
            yield self.get_resource(name)


    def order_up(self, ids):
        order = self.get_ordered_values()
        order = list(order)
        for id in ids:
            index = order.index(id)
            if index > 0:
                order.remove(id)
                order.insert(index - 1, id)
        # Update the order
        self.set_value('order', order)


    def order_down(self, ids):
        order = self.get_ordered_values()
        order = list(order)
        for id in ids:
            index = order.index(id)
            order.remove(id)
            order.insert(index + 1, id)
        # Update the order
        self.set_value('order', order)


    def order_top(self, ids):
        order = self.get_ordered_values()
        order = list(order)
        order = ids + [ id for id in order if id not in ids ]
        # Update the order
        self.set_value('order', order)


    def order_bottom(self, ids):
        order = self.get_ordered_values()
        order = list(order)
        order = [ id for id in order if id not in ids ] + ids
        # Update the order
        self.set_value('order', order)


    def order_add(self, ids):
        order = self.get_ordered_values()
        order = list(order)
        order = [ id for id in order if id not in ids ] + ids
        # Update the order
        self.set_value('order', order)


    def order_remove(self, ids):
        order = self.get_ordered_values()
        order = list(order)
        order = [ id for id in order if id not in ids ]
        # Update the order
        self.set_value('order', order)


    # Views
    browse_content = OrderedFolder_BrowseContent
