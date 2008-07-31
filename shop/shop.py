# -*- coding: UTF-8 -*-
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

# Import from the Standard Library

# Import from itools
from itools.gettext import MSG
from itools.stl import stl

# Import from ikaaro
from ikaaro.folder import Folder
from ikaaro.registry import register_object_class

# Import from Here
from products import Product, Book
from orders import Orders
from cart import Cart


class Shop(Folder):

    class_id = 'shop'
    class_title = MSG(u'Shop')
    class_description = MSG(u'E-commerce Shop')
    #class_icon16 = 'images/xxx.png'
    #class_icon48 = 'images/xxx.png'
    class_views = Folder.class_views + [['view_cart'], ['orders']]

    __fixed_handlers__ = ['orders']


    def get_document_types(self):
        return [Book]


    @staticmethod
    def _make_object(cls, folder, name):
        # Add a shop
        Folder._make_object(cls, folder, name)
        # Add a container for orders
        kw = {'dc:title': {'en': u"Our orders"}}
        metadata = Orders.build_metadata(**kw)
        folder.set_handler('%s/orders.metadata' % name, metadata)


    orders__label__ = u'Orders'
    orders__access__ = True
    orders__icon__ = 'view.png'
    def orders(self, context):
        return context.uri.resolve('orders')

    ################################################################
    # Cart management
    ################################################################

    view_small_cart__access__ = True
    def view_small_cart(self, context):
        cart = Cart()
        products = cart.get_products(context, self)
        uri = '%s/;view_cart' % context.resource.get_pathto(self)
        namespace = {'products': [],
                     'nb_product': len(products),
                     'cart_link': uri}
        for product, quantity in products:
            namespace['products'].append({'title': product.get_title(),
                                          'quantity': quantity})

        handler = self.get_object('/ui/shop/Cart_view.xml')
        return stl(handler, namespace)


    view_cart__label__ = u'Cart'
    view_cart__access__ = True
    view_cart__icon__ = 'view.png'
    def view_cart(self, context):
        context.styles.append('/ui/shop/style.css') # XXX style
        namespace = {'products': []}
        # Get cart
        cart = Cart()
        # Get products informations
        total = 0
        for product, quantity in cart.get_products(context, self):
            # links
            link_add = ';cart?product=%s&action=add' % product.name
            link_remove = ';cart?product=%s&action=remove' % product.name
            link_delete = ';cart?product=%s&action=delete' % product.name
            # Price
            price = product.get_property('price')
            vat = product.get_property('vat')
            price_after_vat = price + (price * vat/100)
            price_total = price_after_vat * quantity
            # All
            product = ({'name': product.name,
                        'title': product.get_title(),
                        'uri': self.get_pathto(product),
                        'quantity': quantity,
                        'price_before_vat': price,
                        'price_after_vat': price_after_vat,
                        'price_total': price_total,
                        'link_add': link_add,
                        'link_remove': link_remove,
                        'link_delete': link_delete,
                        })
            total = total + price_total
            namespace['products'].append(product)
            namespace['link_clear'] = ';cart?action=clear'
        namespace['total'] = total

        handler = self.get_object('/ui/shop/Shop_view_cart.xml')
        return stl(handler, namespace)


    cart__access__ = True
    def cart(self, context):
        action = context.get_form_value('action')
        if(action=='clear'):
            Cart().clear()
        else:
            product = context.get_form_value('product')
            product = self.get_object('%s' % product)
            if(action=='add'):
                Cart().add_product(product.name)
            elif(action=='remove'):
                Cart().remove_product(product.name)
            elif(action=='delete'):
                Cart().delete_product(product.name)
        return context.come_back(None)


register_object_class(Shop)
