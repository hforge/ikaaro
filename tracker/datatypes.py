# -*- coding: UTF-8 -*-
# Copyright (C) 2008 David Versmisse <david.versmisse@itaapy.com>
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
from operator import itemgetter

# Import from itools
from itools.datatypes import Enumerate, String, Integer, Boolean
from itools.web import get_context



def _get_tracker():
    from tracker import Tracker
    # Find the tracker
    resource = get_context().resource
    if isinstance(resource, Tracker):
        return resource
    else:
        return resource.parent



class TrackerList(Enumerate):

    @staticmethod
    def decode(value):
        if not value:
            return None
        return int(value)


    @staticmethod
    def encode(value):
        if value is None:
            return ''
        return str(value)


    @classmethod
    def get_options(cls):
        tracker = _get_tracker()
        elements = tracker.get_resource(cls.element).handler
        return [{'name': record.id,
                 'value': elements.get_record_value(record, 'title')}
                for record in elements.get_records()]



class ProductInfoList(Enumerate):

    @staticmethod
    def decode(value):
        if not value:
            return None
        return int(value)


    @staticmethod
    def encode(value):
        if value is None:
            return ''
        return str(value)


    @classmethod
    def get_options(cls):
        tracker = _get_tracker()
        products = tracker.get_resource('product').handler
        elements = tracker.get_resource(cls.element).handler

        options = []
        for record in elements.get_records():
            title = elements.get_record_value(record, 'title')
            product_id = elements.get_record_value(record, 'product')

            # Product title
            if product_id is None:
                continue
            product_id = int(product_id)
            product_record = products.get_record(product_id)
            product_title = products.get_record_value(product_record, 'title')

            options.append({'name': record.id,
                            'value': '%s - %s' % (product_title, title)})
        return options


    @classmethod
    def is_valid(cls, name):
        # Get the product number
        product =  get_context().get_form_value('product')
        if product is None:
            return True
        product = int(product)

        # Match our choice ?
        choice = int(name)
        tracker = _get_tracker()
        elements = tracker.get_resource(cls.element).handler
        record = elements.get_record(choice)
        product_id = int(elements.get_record_value(record, 'product'))

        return product_id == product



class UsersList(Enumerate):
    @classmethod
    def get_options(cls):
        site_root = get_context().site_root
        users = site_root.get_resource('/users')
        options = [{'name': x,
                    'value': users.get_resource(x).get_title()}
                    for x in site_root.get_members()]
        options.sort(key=itemgetter('value'))
        return options



# Issue Fields
issue_fields = {
    'title': String(mandatory=True),
    'product': TrackerList(element='product', mandatory=True),
    'module': ProductInfoList(element='module'),
    'version': ProductInfoList(element='version'),
    'type': TrackerList(element='type', mandatory=True),
    'state': TrackerList(element='state', mandatory=True),
    'priority': TrackerList(element='priority'),
    'assigned_to': UsersList,
    'cc_list': UsersList(multiple=True),
    'comment': String,
    'file': String}






