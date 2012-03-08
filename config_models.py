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

# Import from itools
from itools.gettext import MSG

# Import from ikaaro
from autoadd import AutoAdd
from autoedit import AutoEdit
from autoform import CheckboxWidget, RadioWidget, SelectWidget
from buttons import Remove_BrowseButton
from config import Configuration
from config_common import NewResource_Local
from fields import Boolean_Field, Date_Field, Integer_Field, Select_Field
from fields import Text_Field, Textarea_Field
from folder import Folder
from folder_views import Folder_BrowseContent
from order import OrderedFolder, OrderedFolder_BrowseContent
from resource_ import DBResource


class FieldType_Field(Select_Field):

    options = [
        {'name': 'boolean', 'value': MSG(u'Boolean')},
        {'name': 'date', 'value': MSG(u'Date')},
        {'name': 'integer', 'value': MSG(u'Integer')},
        {'name': 'text', 'value': MSG(u'Text')},
        {'name': 'textarea', 'value': MSG(u'Textarea')}]

    fields_map = {
        'boolean': Boolean_Field,
        'date': Date_Field,
        'integer': Integer_Field,
        'text': Text_Field,
        'textarea': Textarea_Field}



class ModelField_Base(DBResource):

    # Fields
    required = Boolean_Field(title=MSG(u'Required'))
    multiple = Boolean_Field(title=MSG(u'Multiple'))
    tip = Text_Field(title=MSG(u'Tip'))


    def get_owner(self):
        return self.parent.get_owner()


    def set_value(self, name, value, language=None):
        proxy = super(ModelField_Base, self)
        has_changed = proxy.set_value(name, value, language)
        if has_changed:
            class_id = str(self.parent.abspath)
            self.database._resources_registry.pop(class_id, None)

        return has_changed


    def get_field_kw(self, field):
        return {'multiple': self.get_value('multiple'),
                'required': self.get_value('required'),
                'title': self.get_title(),
                'widget': field.widget(tip=self.get_value('tip'))}


    # Views
    _fields = ['title', 'required', 'multiple', 'tip']
    new_instance = AutoAdd(fields=_fields, automatic_resource_name=True)
    edit = AutoEdit(fields=_fields)



class ModelField_Inherited(ModelField_Base):

    class_id = 'model-field-inherited'
    class_title = MSG(u'Inherited field')
    class_views = ['edit', 'commit_log']



class ModelField_Standard(ModelField_Base):

    class_id = 'model-field-standard'
    class_title = MSG(u'Standard field')

    # Fields
    field_type = FieldType_Field(required=True, title=MSG(u'Field type'))

    # API
    def build_field(self):
        field_type = self.get_value('field_type')
        field = self.field_type.fields_map[field_type]
        field_kw = self.get_field_kw(field)
        return field(**field_kw)

    # Views
    class_views = ['edit', 'commit_log']
    _fields = ModelField_Base._fields + ['field_type']
    new_instance = ModelField_Base.new_instance(fields=_fields)
    edit = AutoEdit(fields=_fields)



class Choice(DBResource):

    class_id = 'model-field-choice'
    class_title = MSG(u'Choice')

    # Views
    class_views = ['edit', 'commit_log']
    new_instance = AutoAdd(fields=['title'])



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
    table_actions = [Remove_BrowseButton]


class ChoicesWidget_Field(Select_Field):

    options = [{'name': 'radio-checkbox', 'value': u'Radio/Checkbox'},
               {'name': 'select', 'value': u'Select'}]


class ModelField_Choices(OrderedFolder, ModelField_Base):

    class_id = 'model-field-choices'
    class_title = MSG(u'Choices field')

    # Fields
    choices_widget = ChoicesWidget_Field(title=MSG(u'Widget to use'),
                                         required=True)

    def get_document_types(self):
        return [Choice]

    # API
    def build_field(self):
        options = [ {'name': x.name, 'value': x.get_title()}
                    for x in self.get_resources_in_order() ]
        field = Select_Field(widget=self.get_widget())
        field_kw = self.get_field_kw(field)
        return field(options=options, **field_kw)


    def get_widget(self):
        if self.get_value('choices_widget') == 'radio-checkbox':
            if self.get_value('multiple'):
                return CheckboxWidget
            return RadioWidget
        return SelectWidget

    # Views
    class_views = ['browse_content', 'add_choice', 'edit', 'commit_log']
    browse_content = ModelField_Choices_Browse
    add_choice = NewResource_Local(title=MSG(u'Add choice'))

    _fields = ModelField_Base._fields + ['choices_widget']
    new_instance = ModelField_Base.new_instance(fields=_fields)
    edit = AutoEdit(fields=_fields)



###########################################################################
# The model resource
###########################################################################
class Model_NewInstance(AutoAdd):

    fields = ['title']

    def make_new_resource(self, resource, context, form):
        proxy = super(Model_NewInstance, self)
        child = proxy.make_new_resource(resource, context, form)
        if child is None:
            return

        # Create the inherited fields
        for field_name, field in child.base_class.get_fields():
            if not field.readonly:
                child.make_resource(field_name, ModelField_Inherited)

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
    table_actions = [Remove_BrowseButton]



class Model(OrderedFolder):

    class_id = '-model'
    class_title = MSG(u'Base model')
    class_description = MSG(u'...')

    # Fields
    title = Folder.title(required=True)

    # Views
    class_views = ['browse_content', 'add_field', 'edit', 'commit_log']
    browse_content = Model_Browse
    new_instance = Model_NewInstance
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


    def get_model_fields(self):
        """Return the resources that represent a field.
        """
        return [ x for x in self.get_resources_in_order()
                 if isinstance(x, ModelField_Base) ]


    def build_resource_class(self):
        # bases
        base_class = self.base_class
        bases = (base_class,)
        # dict
        class_dict = {
            'class_id': str(self.abspath),
            'class_title': MSG(self.get_value('title')),
            'fields_soft': True, # dynamic classes are fragile
            }

        fields = []
        for field_name in base_class.fields:
            field = base_class.get_field(field_name)
            if field and field.readonly:
                fields.append(field_name)

        for resource in self.get_model_fields():
            field_name = resource.name
            if not isinstance(resource, ModelField_Inherited):
                class_dict[field_name] = resource.build_field()
            fields.append(field_name)
        class_dict['fields'] = fields

        return type(self.name, bases, class_dict)


    def set_value(self, name, value, language=None):
        has_changed = super(Model, self).set_value(name, value, language)
        if has_changed:
            class_id = str(self.abspath)
            self.database._resources_registry.pop(class_id, None)

        return has_changed


###########################################################################
# The configuration
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
    table_actions = [Remove_BrowseButton]



class ConfigModels(Folder):

    class_id = 'config-models'
    class_title = MSG(u'Content models')
    class_description = MSG(u'Define new types of content resources.')

    # Configuration
    config_name = 'models'
    config_group = 'content'

    # Views
    class_views = ['browse_content', 'add_model', 'edit', 'commit_log']
    browse_content = ConfigModels_Browse
    add_model = NewResource_Local(title=MSG(u'Add model'))

    def get_document_types(self):
        return [Model]


# Register
#Configuration.register_module(ConfigModels)
