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
from itools.core import thingy_lazy_property
from itools.core import OrderedDict
from itools.datatypes import Enumerate, Unicode
from itools.http import get_context
from itools.web import choice_field



class tracker_choice_field(choice_field):

    @thingy_lazy_property
    def values(self):
        tracker = self.view.resource.get_site_root().get_resource('tracker')
        table = tracker.get_resource(self.name).handler

        values = OrderedDict()
        for record in table.get_records_in_order():
            title = table.get_record_value(record, 'title')
            values[record.id] = {'title': title}

        return values



class product_choice_field(choice_field):

    @thingy_lazy_property
    def values(self):
        tracker = self.view.resource.get_site_root().get_resource('tracker')
        products = tracker.get_resource('product').handler
        elements = tracker.get_resource(self.name).handler

        values = OrderedDict()
        for record in elements.get_records_in_order():
            # Product title
            product_id = elements.get_record_value(record, 'product')
            if product_id is None:
                continue

            product_id = int(product_id)
            product_record = products.get_record(product_id)
            product_title = products.get_record_value(product_record, 'title')

            title = elements.get_record_value(record, 'title')
            values[record.id] = {'title': '%s - %s' % (product_title, title)}

        return values


#   def is_valid(cls, name):
#       # Get the product number
#       product =  get_context().get_form_value('product')
#       if product is None:
#           return True
#       product = int(product)

#       # Match our choice ?
#       choice = int(name)
#       elements = cls.tracker.get_resource(cls.element).handler
#       record = elements.get_record(choice)
#       product_id = int(elements.get_record_value(record, 'product'))

#       return product_id == product



class users_choice_field(choice_field):

    excluded_roles = None

    @thingy_lazy_property
    def values(self):
        users = self.view.resource.get_site_root().get_resource('users')

        values = OrderedDict()
        for user in users.get_resources():
            if excluded_roles and user.get_value('role') in excluded_roles:
                continue
            values[user.get_name()] = {'title': user.get_title()}

        values.sort(key=itemgetter('title'))
        return values

