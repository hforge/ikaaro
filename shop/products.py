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
from itools.datatypes import Unicode, Integer, Decimal
from itools.stl import stl
from itools.handlers import checkid
from itools.web import FormError

# Import from ikaaro
from ikaaro.folder import Folder
from ikaaro.file import File
from ikaaro.registry import register_object_class
from ikaaro.messages import MSG_MISSING_OR_INVALID, MSG_CHANGES_SAVED

# Import from Here
from cart import Cart


class Product(Folder):

    class_id = 'product'
    class_title = u'A product'
    class_description = u'A product'
    #class_icon16 = 'images/xxx.png'
    #class_icon48 = 'images/xxx.png'
    class_views = [['view'],
                   ['edit_form'],
                   ['browse_content?mode=list',
                    'browse_content?mode=image'],
                   ['new_resource_form']]


    product_fields = {'title': Unicode(mandatory=True),
                      'description': Unicode(mandatory=True),
                      'price': Decimal(mandatory=True),
                      'vat': Decimal(mandatory=True),
                      'stock': Integer(mandatory=True)}


    def get_document_types(self):
        return [File]


    @classmethod
    def get_metadata_schema(cls):
        schema = Folder.get_metadata_schema()
        schema['price'] = Decimal
        schema['vat'] = Decimal
        schema['stock'] = Integer
        return schema


    @staticmethod
    def new_instance_form(cls, context):
        namespace = context.build_form_namespace(cls.product_fields)
        namespace['class_id'] = cls.class_id
        uri = 'ui/shop/%s_new_instance.xml' % cls.class_id
        handler = context.root.get_object(uri)
        return stl(handler, namespace)


    @staticmethod
    def new_instance(cls, container, context):
        try:
            form = context.check_form_input(cls.product_fields)
        except FormError:
            return context.come_back(MSG_MISSING_OR_INVALID, keep=True)
        title = form['title']

        # Check the name
        name = title.strip()
        if not name:
            return context.come_back(MSG_NAME_MISSING)

        name = checkid(name)
        if name is None:
            return context.come_back(MSG_BAD_NAME)

        # Check the name is free
        if container.has_object(name):
            return context.come_back(MSG_NAME_CLASH)

        object = cls.make_object(cls, container, name)
        # The metadata
        metadata = object.metadata
        language = container.get_content_language(context)
        metadata.set_property('title', title, language=language)
        # Properties
        for property in cls.product_fields:
            metadata.set_property(property, form[property])

        goto = './;%s' % container.get_firstview()
        return context.come_back(u'Product created!', goto=goto)


    def get_context_menu_base(self):
        return self.parent


    def get_namespace(self):
        namespace = {}
        for property in self.product_fields:
            namespace[property] = self.get_property(property)
        return namespace


    view__access__ = True
    view__label__ = u'View'
    view__icon__ = 'view.png'
    def view(self, context):
        namespace = self.get_namespace()
        shop_root = self.parent
        namespace['cart'] = shop_root.view_small_cart(context)
        handler = self.get_object('/ui/shop/%s_view.xml' % self.class_id)
        return stl(handler, namespace)


    edit_form__access__ = 'is_admin'
    edit_form__label__ = u'Edit'
    edit_form__icon__ = 'edit.png'
    def edit_form(self, context):
        namespace = context.build_form_namespace(self.product_fields,
                                                 self.get_property)
        handler = self.get_object('/ui/shop/%s_edit.xml' % self.class_id)
        return stl(handler, namespace)


    edit__access__ = 'is_admin'
    def edit(self, context):
        # Check the product properties
        try:
            form = context.check_form_input(self.product_fields)
        except FormError:
            return context.come_back(MSG_MISSING_OR_INVALID, keep=True)
        # Save changes
        for property in self.product_fields:
            self.set_property(property, form[property])

        return context.come_back(MSG_CHANGES_SAVED)


    add_to_cart__label__ = u'Add to cart'
    add_to_cart__access__ = True
    def add_to_cart(self, context):
        cart = Cart()
        cart.add_product(self.name)
        return context.come_back(u'Product added to the cart')


class Book(Product):

    class_id = 'book'
    class_title = u'Book'

    product_fields = Product.product_fields
    product_fields.update({'subject': Unicode(mandatory=True),
                           'author': Unicode(mandatory=True),
                           'publisher': Unicode(mandatory=True),
                           'isbn': Integer(mandatory=True)})


    @classmethod
    def get_metadata_schema(cls):
        schema = Product.get_metadata_schema()
        schema['author'] = Unicode
        schema['publisher'] = Unicode
        schema['isbn'] = Integer
        return schema


register_object_class(Product)
register_object_class(Book)
