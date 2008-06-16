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
from itools.web import get_context


class Cart(object):

    #TODO: replace [(name, 1)] to a dict {'name': 1} ?

    def __init__(self):
        context = get_context()
        if not context.has_cookie('shopping_cart'):
            context.set_cookie('shopping_cart', 1)
            self.clear()


    def get_products(self, context, shop_root):
        """Return the list of products in cart"""
        products = []
        for name, quantity in self.get_list_products():
            if shop_root.has_object('%s' % name):
                product = shop_root.get_object('%s' % name)
                products.append((product, quantity))
            else:
                self.remove_product(name, quantity)
        return products


    def get_list_products(self):
        """The transform an cookie value (str) as:
        product1:quantity@product2:quantity
        in a list of tuple as:
        [(product1, quantity), (product2, quantity) ...]"""
        products = get_context().get_cookie('shopping_cart_products')
        if not products:
            return []
        products = products.split('@')
        list = []
        for product in products:
            name, quantity = product.split(':')
            list.append((name,int(quantity)))
        return list or []


    def set_list_products(self, products):
        """This method transform a list of tuple as
        [(product_name, quantity), ...]
        in a str as :
        product_name:quantity@
        """
        context = get_context()
        list = []
        for product in products:
            list.append('%s:%s' % product)
        context.set_cookie('shopping_cart_products', '@'.join(list))


    def manage_product(self, name, quantity=0):
        context = get_context()
        # Check if product already in cart
        products = self.get_list_products()
        for i, product in enumerate(products):
            p_name, p_quantity = product
            if(p_name==name):
                new_quantity = p_quantity + quantity
                if new_quantity == 0:
                    # Remove the product
                    products.remove(products[i])
                else:
                    products[i] = (p_name, p_quantity + quantity)
                self.set_list_products(products)
                return
        # You can only remove product already in cart
        if quantity < 0:
            return
        # Product not in cart
        products.append((name, quantity))
        self.set_list_products(products)


    def add_product(self, name, quantity=1):
        self.manage_product(name, quantity)


    def remove_product(self, name, quantity=-1):
        self.manage_product(name, quantity)


    def delete_product(self, name):
        context = get_context()
        products = self.get_list_products()
        # Check if product already in cart
        for i, product in enumerate(products):
            p_name, p_quantity = product
            if(p_name==name):
                products.remove(products[i])
        self.set_list_products(products)


    def clear(self):
        self.set_list_products([])

