# -*- coding: UTF-8 -*-
# Copyright (C) 2011 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from itools.core import proto_property
from itools.gettext import MSG
from itools.web import get_context

# Import from ikaaro
from autoedit import AutoEdit
from buttons import RemoveButton
from config import Configuration
from config_common import NewResource_Local, NewInstance_Local
from database import Database
from fields import Select_Field
from fields import Integer_Field, Text_Field
from folder import Folder
from folder_views import Folder_BrowseContent
from order import OrderedFolder, OrderedFolder_BrowseContent
from resource_ import DBResource


class FieldType_Field(Select_Field):

    options = [
        {'name': 'text', 'value': MSG(u'Text')},
        {'name': 'integer', 'value': MSG(u'Integer')}]


class ModelField_Base(DBResource):

    def set_value(self, name, value, language=None):
        proxy = super(ModelField_Base, self)
        has_changed = proxy.set_value(name, value, language)
        if has_changed:
            class_id = str(self.parent.abspath)
            Database.resources_registry.pop(class_id, None)

        return has_changed



class ModelField_Inherited(ModelField_Base):

    class_id = 'model-field-inherited'
    class_title = MSG(u'Inherited field')
    class_views = ['edit', 'commit_log']



class ModelField_Standard(ModelField_Base):

    class_id = 'model-field-standard'
    class_title = MSG(u'Standard field')

    # Fields
    fields = DBResource.fields + ['field_type']
    field_type = FieldType_Field(required=True, title=MSG(u'Field type'))

    # API
    def build_field(self):
        fields_map = {
            'text': Text_Field,
            'integer': Integer_Field}

        field_type = self.get_value('field_type')
        return fields_map[field_type]

    # Views
    class_views = ['edit', 'commit_log']
    new_instance = NewInstance_Local(fields=['field_type', 'title'])
    edit = AutoEdit(fields=['field_type', 'title'])



class Choice(DBResource):

    class_id = 'model-field-choice'
    class_title = MSG(u'Choice')

    # Views
    class_views = ['edit', 'commit_log']
    new_instance = NewInstance_Local(fields=['title'])



class ModelField_Choices_Browse(OrderedFolder_BrowseContent):

    search_widgets = None
    depth = 1

    table_columns = [
        ('checkbox', None),
        ('icon', None),
        ('abspath', MSG(u'Path')),
        ('title', MSG(u'Title')),
        ('format', MSG(u'Type')),
        ('mtime', MSG(u'Last Modified')),
        ('last_author', MSG(u'Last Author')),
        ('order', MSG(u'Order'))]
    table_actions = [RemoveButton]



class ModelField_Choices(OrderedFolder, ModelField_Base):

    class_id = 'model-field-choices'
    class_title = MSG(u'Choices field')

    def get_document_types(self):
        return [Choice]

    # API
    def build_field(self):
        options = [ {'name': x, 'value': self.get_resource(x).get_title()}
                    for x in self.get_ordered_values() ]
        return Select_Field(options=options)

    # Views
    class_views = ['browse_content', 'add_choice', 'edit', 'commit_log']
    browse_content = ModelField_Choices_Browse()
    new_instance = NewInstance_Local(fields=['title'])
    add_choice = NewResource_Local(title=MSG(u'Add choice'))



###########################################################################
# The model resource
###########################################################################
models_registry = set()

def register_model_base_class(cls):
    models_registry.add(cls.class_id)


def unregister_model_base_class(cls):
    models_registry.discard(cls.class_id)



class BaseClass_Field(Select_Field):

    @proto_property
    def options(self):
        database = get_context().database
        options = [
            {'name': x, 'value': database.get_resource_class(x).class_title}
            for x in models_registry ]
        options.sort(key=itemgetter('value'))
        return options



class Model_NewInstance(NewInstance_Local):

    fields = ['base_class', 'title']

    def make_new_resource(self, resource, context, form):
        proxy = super(Model_NewInstance, self)
        child = proxy.make_new_resource(resource, context, form)
        if child is None:
            return

        # Create the inherited fields
        field_names = []
        class_id = child.get_value('base_class')
        cls = child.database.get_resource_class(class_id)
        for field_name, field in cls.get_fields():
            if not field.readonly:
                child.make_resource(field_name, ModelField_Inherited)
                field_names.append(field_name)

        # Ok
        return child



class Model_Browse(OrderedFolder_BrowseContent):

    search_widgets = None
    depth = 1

    table_columns = [
        ('checkbox', None),
        ('icon', None),
        ('abspath', MSG(u'Path')),
        ('title', MSG(u'Title')),
        ('format', MSG(u'Type')),
        ('mtime', MSG(u'Last Modified')),
        ('last_author', MSG(u'Last Author')),
        ('order', MSG(u'Order'))]
    table_actions = [RemoveButton]



class Model(OrderedFolder):

    class_id = 'model'
    class_title = MSG(u'...')
    class_description = MSG(u'...')

    # Fields
    fields = Folder.fields + ['base_class']
    base_class = BaseClass_Field(required=True, title=MSG(u'Base class'))
    title = Folder.title(required=True)

    # Views
    class_views = ['browse_content', 'add_field', 'edit', 'commit_log']
    browse_content = Model_Browse()
    new_instance = Model_NewInstance()
    add_field = NewResource_Local(title=MSG(u'Add field'))

    # Order configuration
    allow_to_unorder_items = True

    def get_document_types(self):
        return [ModelField_Standard, ModelField_Choices]


    @property
    def __fixed_handlers__(self):
        return []
        # XXX To allow ordering, resources should not be fixed handlers
        #return [ x.name for x in self.get_resources()
        #         if isinstance(x, ModelField_Inherited) ]


    def build_resource_class(self):
        # bases
        base_class = self.get_value('base_class')
        base_class = self.database.get_resource_class(base_class)
        bases = (base_class,)
        # dict
        class_dict = {
            'class_id': str(self.abspath),
            'class_title': MSG(self.get_value('title'))}

        fields = []
        for field_name in base_class.fields:
            field = base_class.get_field(field_name)
            if field and field.readonly:
                fields.append(field_name)

        for field_name in self.get_ordered_values():
            resource = self.get_resource(field_name)
            if not isinstance(resource, ModelField_Inherited):
                field = resource.build_field()
                class_dict[field_name] = field(title=resource.get_title())
            fields.append(field_name)
        class_dict['fields'] = fields

        return type(self.name, bases, class_dict)


    def set_value(self, name, value, language=None):
        has_changed = super(Model, self).set_value(name, value, language)
        if has_changed:
            class_id = str(self.abspath)
            Database.resources_registry.pop(class_id, None)

        return has_changed


###########################################################################
# The configuration plugin
###########################################################################
class ConfigModels_Browse(Folder_BrowseContent):

    search_widgets = None
    depth = 1

    table_columns = [
        ('checkbox', None),
        ('abspath', MSG(u'Path')),
        ('title', MSG(u'Title')),
        ('base_class', MSG(u'Base class')),
        ('mtime', MSG(u'Last Modified')),
        ('last_author', MSG(u'Last Author'))]
    table_actions = [RemoveButton]



class ConfigModels(Folder):

    class_id = 'config-models'
    class_title = MSG(u'Content models')
    class_description = MSG(u'Define new types of content resources.')

    # Configuration
    config_name = 'models'
    config_group = 'content'

    # Views
    class_views = ['browse_content', 'add_model', 'edit', 'commit_log']
    browse_content = ConfigModels_Browse()
    add_model = NewResource_Local(title=MSG(u'Add model'))

    def get_document_types(self):
        return [Model]


Configuration.register_plugin(ConfigModels)
