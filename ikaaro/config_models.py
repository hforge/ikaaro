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
from .views.folder_views import Folder_BrowseContent

# Import from ikaaro
from .autoadd import AutoAdd
from .autoedit import AutoEdit
from .buttons import Remove_BrowseButton
from .fields import Boolean_Field, Date_Field, Email_Field, Integer_Field
from .fields import Select_Field, Text_Field, Textarea_Field
from .folder import Folder
from .order import OrderedFolder, OrderedFolder_BrowseContent
from .resource_ import DBResource
from .views.folder_views import Folder_NewResource
from .widgets import CheckboxWidget, RadioWidget, SelectWidget


class FieldType_Field(Select_Field):

    options = [
        {'name': 'boolean', 'value': MSG('Boolean')},
        {'name': 'date', 'value': MSG('Date')},
        {'name': 'email', 'value': MSG('Email')},
        {'name': 'integer', 'value': MSG('Integer')},
        {'name': 'text', 'value': MSG('Text')},
        {'name': 'textarea', 'value': MSG('Textarea')}]

    fields_map = {
        'boolean': Boolean_Field,
        'date': Date_Field,
        'email': Email_Field,
        'integer': Integer_Field,
        'text': Text_Field,
        'textarea': Textarea_Field}



class ModelField_Base(DBResource):

    # Fields
    required = Boolean_Field(title=MSG('Required'))
    multiple = Boolean_Field(title=MSG('Multiple'))
    tip = Text_Field(title=MSG('Tip'))


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
    class_title = MSG('Inherited field')
    class_views = ['edit']



class ModelField_Standard(ModelField_Base):

    class_id = 'model-field-standard'
    class_title = MSG('Standard field')

    # Fields
    field_type = FieldType_Field(required=True, title=MSG('Field type'))

    # API
    def build_field(self):
        field_type = self.get_value('field_type')
        field = self.field_type.fields_map[field_type]
        field_kw = self.get_field_kw(field)
        return field(**field_kw)

    # Views
    class_views = ['edit']
    _fields = ModelField_Base._fields + ['field_type']
    new_instance = AutoAdd(fields=_fields, automatic_resource_name=True)
    edit = AutoEdit(fields=_fields)



class Choice(DBResource):

    class_id = 'model-field-choice'
    class_title = MSG('Choice')

    # Views
    class_views = ['edit']
    new_instance = AutoAdd(fields=['title'])



class ModelField_Choices_Browse(OrderedFolder_BrowseContent):

    search_widgets = None
    depth = 1

    table_columns = [
        ('checkbox', None),
        ('icon', None),
        ('abspath', MSG('Path')),
        ('title', MSG('Title')),
        ('format', MSG('Type')),
        ('mtime', MSG('Last Modified')),
        ('last_author', MSG('Last Author')),
        ('order', MSG('Order'))]
    table_actions = [Remove_BrowseButton]


class ChoicesWidget_Field(Select_Field):

    options = [{'name': 'radio-checkbox', 'value': 'Radio/Checkbox'},
               {'name': 'select', 'value': 'Select'}]


class ModelField_Choices(OrderedFolder, ModelField_Base):

    class_id = 'model-field-choices'
    class_title = MSG('Choices field')

    # Fields
    choices_widget = ChoicesWidget_Field(title=MSG('Widget to use'),
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
    class_views = ['browse_content', 'add_choice', 'edit']
    browse_content = ModelField_Choices_Browse()
    add_choice = Folder_NewResource(title=MSG('Add choice'))

    _fields = ModelField_Base._fields + ['choices_widget']
    new_instance = AutoAdd(fields=_fields, automatic_resource_name=True)
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
        ('abspath', MSG('Path')),
        ('title', MSG('Title')),
        ('format', MSG('Type')),
        ('mtime', MSG('Last Modified')),
        ('last_author', MSG('Last Author')),
        ('order', MSG('Order'))]
    table_actions = [Remove_BrowseButton]



class Model(OrderedFolder):

    class_id = '-model'
    class_title = MSG('Base model')
    class_description = MSG('...')

    # Fields
    title = Text_Field(indexed=True, stored=True, title=MSG('Title'), required=True)

    # Views
    class_views = ['browse_content', 'add_field', 'edit']
    browse_content = Model_Browse()
    new_instance = Model_NewInstance()
    add_field = Folder_NewResource(title=MSG('Add field'))

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
        title = self.get_value('title')
        class_dict = {
            'class_id': str(self.abspath),
            'class_title': MSG(title) if title else base_class.class_title,
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
        ('abspath', MSG('Path')),
        ('title', MSG('Title')),
        ('base_class', MSG('Base class')),
        ('mtime', MSG('Last Modified')),
        ('last_author', MSG('Last Author'))]
    table_actions = [Remove_BrowseButton]



class ConfigModels(Folder):

    class_id = 'config-models'
    class_title = MSG('Content models')
    class_description = MSG('Define new types of content resources.')

    # Configuration
    config_name = 'models'
    config_group = 'content'

    # Views
    class_views = ['browse_content', 'add_model', 'edit']
    browse_content = ConfigModels_Browse()
    add_model = Folder_NewResource(title=MSG('Add model'))

    def get_document_types(self):
        return [Model]
