# -*- coding: UTF-8 -*-
# Copyright (C) 2009 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from itools.core import OrderedDict
from itools.datatypes import Unicode
from itools.gettext import MSG
from itools.web import choice_field

# Import from ikaaro
from autoform import AutoForm
from fields import NameField
from folder import Folder
from registry import get_resource_class
from table import OrderedTableResource, OrderedTable
from views_new import NewInstance



###########################################################################
# Fields
###########################################################################
class choice_handler(OrderedTable):
    record_properties = {
        'title': Unicode(multiple=True)}



class choice_table(OrderedTableResource):

    class_id = 'choice_field'
    class_handler = choice_handler



class TypeField(choice_field):

    title = MSG(u'Type')
    values = OrderedDict([
        ('choice_field', {'title': MSG(u'Choice')}),
    ])



class Model_AddField(AutoForm):

    access = 'is_admin'
    view_title = MSG(u'Add field')

    # Fields
    name = NameField(required=True)
    type = TypeField(required=True)

    # Autoform
    field_names = ['name', 'type']
    submit_value = MSG(u'Add')


    def action(self):
        name = self.name.value.strip()
        type = self.type.value

        # Add
        cls = get_resource_class(type)
        field = self.resource.make_resource(name, cls)

        # Ok
        context = self.context
        context.message = MSG(u'New field added.')
        location = str(field.path)
        context.created(location)



###########################################################################
# Model
###########################################################################
class Model_NewInstance(NewInstance):

    path = None

    def get_container(self):
        root = self.context.get_resource('/')
        container = root.get_resource('models', soft=True)
        if container:
            return container
        return root.make_resource('models', Folder)


    def get_resource_class(self):
        return Model



class Model(Folder):

    class_id = 'model'
    class_title = MSG(u'Model')
    class_description = MSG(u'...')
    class_views = ['table', 'add_field', 'edit', 'backlinks', 'last_changes']

    # Views
    new_instance = Model_NewInstance
    list = None
    gallery = None

    table = Folder.table()
    table.search = table.search(show=False)
    table.view_title = MSG(u'Fields')

    add_field = Model_AddField()

