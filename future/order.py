# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
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
from itools.datatypes import Tokens
from itools.stl import stl


class OrderAware(object):
    # FIXME backwards compatibility
    # Use "get_orderable_classes"
    orderable_classes = None

    @classmethod
    def get_metadata_schema(cls):
        return {
            'order': Tokens(default=()),
        }


    @classmethod
    def get_orderable_classes(cls):
        return (cls,)


    def get_ordered_names(self, mode='mixed'):
        """Return current order plus the unordered names at the end.
            mode mixed -> ordered + unordered
            mode ordered -> ordered
            mode all -> (ordered, unordered)
            default mode : mixed
        """
        orderable_classes = self.orderable_classes
        if orderable_classes is None:
            orderable_classes = self.get_orderable_classes()
        ordered_names = self.get_property('order')
        objects = self.search_objects(object_class=orderable_classes)
        real_names = [object.name for object in objects]
        ordered = [name for name in ordered_names if name in real_names]
        if mode == 'ordered':
            return ordered
        unordered = [name for name in real_names if name not in ordered_names]
        if mode == 'all':
            return ordered, unordered
        return ordered + unordered


    def get_ordered_objects(self, objects, mode='mixed', reverse=False):
        """Return a sorted list of child handlers or brains of them.
            mode mixed -> ordered + unordered
            mode ordered -> ordered
            mode all -> (ordered, unordered)
            default mode : mixed
        """
        if mode == 'ordered':
            ordered_list = []
            ordered_names = self.get_ordered_names('ordered')
            for object in objects:
                index = ordered_names.index(object.name)
                ordered_list.append((index, object))
            ordered_list.sort(reverse=reverse)
            return [x[1] for x in ordered_list]
        else:
            ordered_list, unordered_list = [], []
            ordered_names, unordered_names = self.get_ordered_names('all')
            for object in objects:
                name = object.name
                if name in ordered_names:
                    index = ordered_names.index(name)
                    ordered_list.append((index, object))
                elif name in unordered_names:
                    index = unordered_names.index(name)
                    unordered_list.append((index, object))
            ordered_list.sort(reverse=reverse)
            unordered_list.sort(reverse=reverse)
            ordered = [x[1] for x in ordered_list]
            unordered = [x[1] for x in unordered_list]
            if mode == 'all':
                return (ordered, unordered)
            return ordered + unordered


    order_form__access__ = 'is_allowed_to_edit'
    order_form__label__ = u"Order"
    order_form__sublabel__ = u"Order"
    order_form__icon__ = 'button_compare.png'
    def order_form(self, context):
        namespace = {}

        here = context.object
        ordered = []
        unordered = []
        names = self.get_ordered_names('all')
        ordered_names, unordered_names = names

        for data in [(ordered_names, ordered), (unordered_names, unordered)]:
            names, l = data
            for name in names:
                object = self.get_object(name)
                ns = self._browse_namespace(object, 16)
                ns['name'] = name
                path = None
                if isinstance(object, OrderAware):
                    path = '%s/;order_form' % name
                ns['path'] = path
                l.append(ns)
        namespace['ordered'] = ordered
        namespace['unordered'] = unordered

        handler = self.get_object('/ui/future/order_items.xml')
        return stl(handler, namespace)


    order_up__access__ = 'is_allowed_to_edit'
    def order_up(self, context):
        names = context.get_form_values('ordered_names')
        if not names:
            return context.come_back(u'Please select the ordered objects' \
                                       ' to order up.')

        ordered_names = self.get_ordered_names('ordered')

        if ordered_names[0] == names[0]:
            return context.come_back(u"Objects already up.")

        temp = list(ordered_names)
        for name in names:
            idx = temp.index(name)
            temp.remove(name)
            temp.insert(idx - 1, name)
        self.set_property('order', tuple(temp))

        message = u"Objects ordered up."
        return context.come_back(message)


    order_down__access__ = 'is_allowed_to_edit'
    def order_down(self, context):
        names = context.get_form_values('ordered_names')
        if not names:
            return context.come_back(
                u"Please select the ordered objects to order down.")

        ordered_names = self.get_ordered_names('ordered')

        if ordered_names[-1] == names[-1]:
            return context.come_back(u"Objects already down.")

        temp = list(ordered_names)
        names.reverse()
        for name in names:
            idx = temp.index(name)
            temp.remove(name)
            temp.insert(idx + 1, name)
        self.set_property('order', tuple(temp))

        message = u"Objects ordered down."
        return context.come_back(message)


    order_top__access__ = 'is_allowed_to_edit'
    def order_top(self, context):
        names = context.get_form_values('ordered_names')
        if not names:
            message = u"Please select the ordered objects to order on top."
            return context.come_back(message)

        ordered_names = self.get_ordered_names('ordered')

        if ordered_names[0] == names[0]:
            message = u"Objects already on top."
            return context.come_back(message)

        temp = names + [name for name in ordered_names if name not in names]
        self.set_property('order', tuple(temp))

        message = u"Objects ordered on top."
        return context.come_back(message)


    order_bottom__access__ = 'is_allowed_to_edit'
    def order_bottom(self, context):
        names = context.get_form_values('ordered_names')
        if not names:
            message = u"Please select the ordered objects to order on bottom."
            return context.come_back(message)

        ordered_names = self.get_ordered_names('ordered')

        if ordered_names[-1] == names[-1]:
            message = u"Objects already on bottom."
            return context.come_back(message)

        temp = [name for name in ordered_names if name not in names] + names
        self.set_property('order', tuple(temp))

        message = u"Objects ordered on bottom."
        return context.come_back(message)


    ordered__access__ = 'is_allowed_to_edit'
    def ordered(self, context):
        names = context.get_form_values('unordered_names')
        if not names:
            message = u'Please select the unordered objects to move ' \
                       'into the ordered category.'
            return context.come_back(message)

        ordered_names, unordered_names = self.get_ordered_names('all')
        temp = list(ordered_names) + [name for name in names]
        self.set_property('order', tuple(temp))

        message = u"Objects moved to ordered category."
        return context.come_back(message)


    unordered__access__ = 'is_allowed_to_edit'
    def unordered(self, context):
        names = context.get_form_values('ordered_names')
        if not names:
            message = u'Please select the ordered objects to move into ' \
                       'the unordered category.'
            return context.come_back(message)

        ordered_names, unordered_names = self.get_ordered_names('all')

        temp = [ name for name in ordered_names if name not in names ]
        self.set_property('order', tuple(temp))

        message = u"Objects moved to ordered category."
        return context.come_back(message)
