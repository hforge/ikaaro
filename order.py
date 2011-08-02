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
from itools.web import INFO, get_context

# Import from ikaaro
from ikaaro.buttons import OrderUpButton, OrderDownButton, OrderTopButton
from ikaaro.buttons import OrderBottomButton, OrderButton, UnOrderButton


###############################################
# OrderAware
###############################################

class OrderAware(object):

    allow_to_unorder_items = False

    def order_up(self, ids):
        order = self.get_ordered_values()
        order = list(order)
        for id in ids:
            index = order.index(id)
            if index > 0:
                order.remove(id)
                order.insert(index - 1, id)
        # Update the order
        self.update_order(order=order)


    def order_down(self, ids):
        order = self.get_ordered_values()
        order = list(order)
        for id in ids:
            index = order.index(id)
            order.remove(id)
            order.insert(index + 1, id)
        # Update the order
        self.update_order(order=order)


    def order_top(self, ids):
        order = self.get_ordered_values()
        order = list(order)
        order = ids + [ id for id in order if id not in ids ]
        # Update the order
        self.update_order(order=order)


    def order_bottom(self, ids):
        order = self.get_ordered_values()
        order = list(order)
        order = [ id for id in order if id not in ids ] + ids
        # Update the order
        self.update_order(order=order)


    def order_add(self, ids):
        order = self.get_ordered_values()
        order = list(order)
        order = [ id for id in order if id not in ids ] + ids
        # Update the order
        self.update_order(order=order)


    def order_remove(self, ids):
        order = self.get_ordered_values()
        order = list(order)
        order = [ id for id in order if id not in ids ]
        # Update the order
        self.update_order(order=order)

    ##############################
    # To override
    ##############################

    def update_order(self, order):
        raise NotImplementedError


    def get_ordered_values(self):
        raise NotImplementedError




class OrderAware_View(object):


    def get_table_actions(self, resource, context):
        actions = [OrderUpButton, OrderDownButton,
                   OrderTopButton, OrderBottomButton]
        if resource.allow_to_unorder_items:
            return actions + [OrderButton, UnOrderButton]
        return actions


    def get_items(self, resource, context):
        raise NotImplementedError


    def get_key_sorted_by_order(self):
        context = get_context()
        ordered_names = list(context.resource.get_ordered_values())
        nb_ordered_names = len(ordered_names)
        def key(item):
            return (ordered_names.index(item.name)
                      if item.name in ordered_names else nb_ordered_names)
        return key

    ######################################################################
    # Order Actions
    ######################################################################
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
