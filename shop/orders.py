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
from string import Template

# Import from itools
from itools import get_abspath
from itools.datatypes import Unicode, String, Integer
from itools.gettext import MSG
from itools.i18n import format_datetime
from itools.pdf import PDFFile
from itools.stl import stl
from itools.web import FormError, MSG_MISSING_OR_INVALID
from itools.xapian import KeywordField, EqQuery
from itools.xml import XMLParser

# Import from ikaaro
from ikaaro.binary import PDF
from ikaaro.folder import Folder
from ikaaro.registry import register_object_class
from ikaaro.workflow import WFTransition, WorkflowAware
from ikaaro.messages import *

# Import from here
from cart import Cart
from workflow import order_workflow


class Orders(Folder):

    class_id = 'orders'
    class_title = MSG(u'Orders')
    class_description = MSG(u'Our orders')
    class_views = Folder.class_views + ['view', 'view_all']
    #class_icon16 = 'images/xxx.png'
    #class_icon48 = 'images/xxx.png'


    def get_document_types(self):
        return [Order]


    view__label__ = u'View my orders'
    view__access__ = 'is_allowed_to_add'
    view__icon__ = 'view.png'
    def view(self, context):
        """Show customer orders"""
        namespace = {}
        root = context.root
        accept = context.accept_language
        # Get values from the request
        size = 20
        sortby = context.get_form_values('sortby', default=['mtime'])
        sortorder = context.get_form_value('sortorder', default='up')
        start = context.get_form_value('batchstart', type=Integer, default=0)
        # The columns
        columns = [('id', u'Order id'),
                   ('mtime', u'Date'),
                   ('state', u'State'),
                   ('pdf', u'Pdf')]
        # Table content
        customer_id = context.user.name
        catalog = context.server.catalog
        results = catalog.search(EqQuery('customer_id', customer_id))
        namespace['nb_orders'] = results.get_n_documents()
        my_orders = results.get_documents(sort_by='name')
        orders = []
        for my_order in my_orders:
            order = root.get_resource(my_order.abspath)
            # Mtime
            mtime = format_datetime(order.get_mtime(), accept)
            # State
            state = order.get_state()
            msg = self.gettext(state['title']).encode('utf-8')
            statename = order.get_statename()
            state = ('<strong class="wf_%s">%s</strong>') % (statename, msg)
            # Pdf
            pdf_img = XMLParser('<img src="/ui/icons/16x16/pdf.png"/>')
            pdf_uri = '%s/order.pdf' % order.name
            # Other
            orders.append({'id': (order.name, order.name),
                           'mtime': mtime,
                           'state': XMLParser(state),
                           'pdf': (pdf_img, pdf_uri)})
        total = len(orders)
        # The actions
        actions = []
        # Batch
        batch = Batch(size=size, msg_1=u'<span>You have one order.</span>',
                      msg_2=u'<span>You have ${n} orders</span>')
        namespace['batch'] = batch.render(start, total, context)
        # Table
        namespace['table'] = table(columns, orders, sortby, sortorder,
                                   actions, self.gettext)

        handler = self.get_resource('/ui/shop/Orders_view.xml')
        return stl(handler, namespace)


    view_all__label__ = u'View all orders'
    view_all__access__ = 'is_allowed_to_add'
    view_all__icon__ = 'view.png'
    def view_all(self, context):
        namespace = {}
        root = context.root
        accept = context.accept_language
        # Get values from the request
        size = 20
        sortby = context.get_form_values('sortby', default=['mtime'])
        sortorder = context.get_form_value('sortorder', default='up')
        start = context.get_form_value('batchstart', type=Integer, default=0)
        # The columns
        columns = [('id', u'Order id'),
                   ('mtime', u'Date'),
                   ('customer', u'customer'),
                   ('state', u'State'),
                   ('pdf', u'Pdf')]
        # Table content
        orders = []
        for order in self.search_objects(object_class=Order):
            # Mtime
            mtime = format_datetime(order.get_mtime(), accept)
            # Customer
            customer_id = order.get_property('customer_id')
            customer = root.get_user(customer_id)
            customer_uri = self.get_pathto(customer)
            # State
            state = order.get_state()
            msg = self.gettext(state['title']).encode('utf-8')
            statename = order.get_statename()
            state = ('<a href="%s/;state_form" class="workflow">'
                     '<strong class="wf_%s">%s</strong>'
                     '</a>') % (self.get_pathto(order), statename, msg)
            # Pdf
            pdf_img = XMLParser('<img src="/ui/images/Pdf16.png"/>')
            pdf_uri = '%s/order.pdf' % order.name
            # Other
            orders.append({'checkbox': True,
                           'id': (order.name, order.name),
                           'mtime': mtime,
                           'customer': (customer.get_title(), customer_uri),
                           'state': XMLParser(state),
                           'pdf': (pdf_img, pdf_uri)})
        total = len(orders)
        # The actions
        message = u'Are you realy sure you want to delete this order ?'
        message = self.gettext(message)
        actions = [('remove', u'Remove', 'button_delete',
                    'return confirmation("%s");' % message.encode('utf_8'))]
        actions = [(x[0], self.gettext(x[1]), x[2], x[3]) for x in actions ]
        # Batch
        batch = Batch(size=size, msg_1=u'<span>There is one order.</span>',
                      msg_2=u'<span>There are ${n} orders</span>')
        namespace['batch'] = batch.render(start, total, context)
        # Table
        namespace['table'] = table(columns, orders, sortby, sortorder,
                                   actions, self.gettext)

        handler = self.get_resource('/ui/shop/Order_view_all.xml')
        return stl(handler, namespace)


    def get_context_menu_base(self):
            return self.parent


class Order(Folder, WorkflowAware):

    class_id = 'order'
    class_title = MSG(u'Order')
    class_description = MSG(u'Create an order in our shop')
    #class_icon16 = 'images/xxx.png'
    #class_icon48 = 'images/xxx.png'
    class_views = Folder.class_views + ['state_form', 'view']

    # Workflow
    workflow = order_workflow
    state_form__access__ = 'is_allowed_to_add'
    state_form__label__ = u'State'


    order_fields = {'address1': Unicode(mandatory=True),
                    'address2': Unicode,
                    'zip': Unicode(mandatory=True),
                    'city': Unicode(mandatory=True),
                    'bp': Integer}


    @classmethod
    def get_metadata_schema(cls):
        schema = Folder.get_metadata_schema()
        schema.update(WorkflowAware.get_metadata_schema())
        schema['customer_id'] = Unicode
        schema['address1'] = Unicode
        schema['address2'] = Unicode
        schema['zip'] = Unicode
        schema['city'] = Unicode
        schema['bp'] = Integer
        return schema


    @staticmethod
    def _make_object(cls, folder, name):
        Folder._make_object(cls, folder, name)
        # Add a FAKE PDF
        path = get_abspath('data/test.pdf')
        handler = PDFFile()
        handler.load_state_from(path)
        kw = {'dc:title': {'en': u"PDF"}}
        metadata = PDF.build_metadata(**kw)
        folder.set_handler('%s/order.pdf' % name, handler)
        folder.set_handler('%s/order.pdf.metadata' % name, metadata)


    @staticmethod
    def new_instance_form(cls, context):
        context.styles.append('/ui/shop/style.css') # XXX style
        namespace = context.build_form_namespace(cls.order_fields)
        namespace['class_id'] = cls.class_id
        namespace['products'] = []
        # Get cart
        cart = Cart()
        cart_products = cart.get_list_products()
        # Get products informations
        total = 0
        for name, quantity in cart_products:
            product = context.resource.parent.get_resource('%s' % name)
            # Price
            price = product.get_property('price')
            vat = product.get_property('vat')
            price_after_vat = price + (price * vat/100)
            price_total = price_after_vat * quantity
            # All
            p = ({'name': product.name,
                  'title': product.get_title(),
                  'uri': context.resource.get_pathto(product),
                  'description': product.get_property('dc:description'),
                  'quantity': quantity,
                  'price_before_vat': price,
                  'price_after_vat': price_after_vat,
                  'price_total': price_total})
            namespace['products'].append(p)
            total = total + price_total
        namespace['total'] = total
        # Customer informations
        namespace['firstname'] = context.user.get_property('firstname')
        namespace['lastname'] = context.user.get_property('lastname')
        namespace['email'] = context.user.get_property('email')

        handler = context.root.get_resource('/ui/shop/Order_new_instance.xml')
        return stl(handler, namespace)


    @staticmethod
    def new_instance(cls, container, context):
        try:
            form = context.check_form_input(cls.order_fields)
        except FormError:
            return context.come_back(MSG_MISSING_OR_INVALID, keep=True)
        # Search a good id for letter
        orders = list(container.search_objects(object_class=Order))
        orders = [int(x.name) for x in orders]
        nb_max = max([0] + orders)
        name = str(int(nb_max) + 1)
        # Title
        title = u'Order number %s' % name
        # Create order
        object = cls.make_object(cls, container, name)
        # Get cart
        cart = Cart()
        cart_products = cart.get_list_products()
        # The metadata
        metadata = object.metadata
        language = container.get_content_language(context)
        metadata.set_property('title', title, language=language)
        # Save command
        metadata.set_property('customer_id', context.user.name)
        metadata.set_property('state', 'open')
        for field in cls.order_fields:
            value = form[field]
            if value:
                metadata.set_property(field, value)
        # Send E-mail confirmation
        customer_mail = context.user.get_property('email')
        admin_mail = context.server.smtp_from
        subject = u'Command confirmation'
        # Template for E-mail (HTML and Text version)
        namespace = {'customer_id': context.user.name,
                     'firstname': context.user.get_property('firstname'),
                     'lastname': context.user.get_property('lastname'),
                     'email': customer_mail,
                     'address1': form['address1'],
                     'address2': form['address2'] or '-',
                     'zip': form['zip'],
                     'city': form['city'],
                     'bp': form['bp'] or '-',
                     'products': []}
        order_price = 0
        for name, quantity in cart_products:
            product = context.resource.parent.get_resource('%s' % name)
            # Reduce the stock
            stock = product.get_property('stock')
            product.set_property('stock', stock - quantity)
            # Price
            price = product.get_property('price')
            vat = product.get_property('vat')
            price_after_vat = price + (price * vat/100)
            price_total = price_after_vat * quantity
            namespace['products'].append({'title': product.get_title(),
                                          'quantity': quantity,
                                          'price_total': price_total})
            order_price += price_total
        namespace['order_price'] = order_price
        # Construct E-mail : Html version TODO
        # Construct E-mail : Text version
        text = ('Hello,\n'
                'We confirm your command in our shop,'
                'it will be delivered as soon as possible.\n'
                'We thanks your for your trust.\n'
                'Please find bellow details about your purchase:\n\n')
        coord_template = ('Address invoicing\n'
                          '-------------------\n\n'
                          'Customer-id: $customer_id\n'
                          'Firstname: $firstname\n'
                          'Lastname: $lastname\n'
                          'E-mail: $email\n'
                          'Address1: $address1\n'
                          'Address2: $address2\n'
                          'Zip: $zip\n'
                          'City: $city\n'
                          'BP: $bp\n\n')
        text += Template(coord_template).substitute(namespace)
        products_template = Template('-----------------------------\n'
                                     '$products\n'
                                     '-----------------------------\n'
                                     'Total price: $order_price \n'
                                     '-----------------------------\n')
        product_template = Template('1 X $title = $price_total')
        products = []
        for product_namespace in namespace['products']:
            products.append(product_template.substitute(product_namespace))
        text += products_template.substitute(order_price=order_price,
                                             products='\n'.join(products))
        # Send mail to customer and admin
        context.root.send_email(customer_mail, subject, text=text)
        context.root.send_email(admin_mail, subject, text=text)
        # Clear the cart
        cart.clear()

        # Come back
        message = u'Order created.'
        return context.come_back(message, goto='./')


    def get_catalog_fields(self):
        fields = Folder.get_catalog_fields(self)
        fields.append(KeywordField('customer_id'))
        return fields


    def get_catalog_values(self):
        indexes = Folder.get_catalog_values(self)
        indexes['customer_id'] = self.get_property('customer_id')
        return indexes


    def get_context_menu_base(self):
            return self.parent.parent


    view__label__ = u'View'
    view__access__ = True
    view__icon__ = 'view.png'
    def view(self, context):
        customer_id = context.user.name
        if self.get_property('customer_id') != customer_id:
            return context.come_back('Forbidden')
        namespace = {'name': self.name,
                     'mtime': self.get_mtime(),
                     'state': self.get_property('state')}
        # Metadata
        for field in self.order_fields:
            namespace[field] = self.get_property(field)
        handler = self.get_resource('/ui/shop/Order_view.xml')

        return stl(handler, namespace)

register_object_class(Orders)
register_object_class(Order)
