# -*- coding: UTF-8 -*-
# Copyright (C) 2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from datetime import date
from operator import itemgetter

# Import from itools
from itools.core import freeze, thingy_property, thingy_lazy_property
from itools.core import OrderedDict
from itools.csv import Property
from itools.datatypes import Date, String, Enumerate
from itools.gettext import MSG
from itools.handlers import checkid
from itools.http import get_context
from itools.web import FormError, hidden_field, choice_field

# Import from ikaaro
from autoform import AutoForm
from fields import title_field
from fields import DateField, NameField
import messages
from registry import get_resource_class, get_document_types



###########################################################################
# The default new-instance form creates the resources in the 'yyyy/mm/dd'
# folder hierarchy, starting from the site-root.
###########################################################################
class TodayDataType(Date):

    def get_default(cls):
        return date.today()



class NewInstanceByDate(AutoForm):
    """This is the base class for all ikaaro forms meant to create and
    add a new resource to the database.
    """

    access = 'is_allowed_to_add'
    submit_value = MSG(u'Add')
    context_menus = freeze([])

    # Schema
    type = hidden_field(source='query')
    title = title_field(value=u'')
    date = DateField(datatype=TodayDataType, required=True, title=MSG(u'Date'))


    def view_title(self):
        type = self.title.value
        if not type:
            return MSG(u'Add resource').gettext()
        cls = get_resource_class(type)
        class_title = cls.class_title.gettext()
        title = MSG(u'Add {class_title}')
        return title.gettext(class_title=class_title)


    def icon(self, resource, **kw):
        type = kw.get('type')
        cls = get_resource_class(type)
        if cls is not None:
            return cls.get_class_icon()
        # Default
        return 'new.png'


    @thingy_lazy_property
    def new_resource_name(self):
        return self.title.value.strip()


    def cook(self, method):
        super(NewInstanceByDate, self).cook(method)
        if method == 'get':
            return

        # Check the name
        name = self.new_resource_name
        if not name:
            raise FormError, messages.MSG_NAME_MISSING

        try:
            name = checkid(name)
        except UnicodeEncodeError:
            name = None

        if name is None:
            raise FormError, messages.MSG_BAD_NAME

        # Check the name is free
        if self.resource.get_resource(name, soft=True) is not None:
            raise FormError, messages.MSG_NAME_CLASH


    def get_date(self):
        return self.date.value


    def get_container(self):
        from folder import Folder

        # The path of the container
        date = self.get_date()
        path = ['%04d' % date.year, '%02d' % date.month, '%02d' % date.day]

        # Get the container, create it if needed
        container = self.context.site_root
        for name in path:
            folder = container.get_resource(name, soft=True)
            if folder is None:
                folder = container.make_resource(name, Folder)
            container = folder

        return container


    def get_resource_class(self):
        return get_resource_class(self.type.value)


    def modify_resource(self, child):
        title = self.title.value
        language = self.resource.get_content_language(self.context)
        title = Property(title, lang=language)
        child.metadata.set_property('title', title)


    def action(self):
        # 1. Get the container
        container = self.get_container()

        # 2. Make the resource
        cls = self.get_resource_class()
        name = self.new_resource_name
        child = container.make_resource(name, cls)

        # 3. Edit the resource
        self.modify_resource(child)

        # 4. Ok
        context = self.context
        context.message = messages.MSG_NEW_RESOURCE
        location = str(child.path)
        context.created(location)



###########################################################################
# The 'NewInstance' view adds a resource to a folder explicitely selected
# in the form.
###########################################################################

class path_field(choice_field):

    mode = 'radio'
    title = MSG(u'Path')

    @thingy_lazy_property
    def values(self):
        # Search
        results = self.view.context.search(is_folder=True)

        # The namespace
        values = []
        for resource in results.get_documents():
            path = str(resource.path)
            values.append((path, {'title': path}))
        values.sort(key=lambda x: x[1]['title'])

        # Ok
        return OrderedDict(values)


    @thingy_lazy_property
    def default(self):
        path = self.view.resource.path
        return str(path)



class NewInstance(NewInstanceByDate):

    name = NameField()
    date = None
    path = path_field()

    field_names = ['title', 'name', 'path']


    @thingy_lazy_property
    def new_resource_name(self):
        # If the name is not explicitly given, use the title
        name = self.name.value
        title = self.title.value.strip()
        return name or title


    def get_container(self):
        path = self.path.value
        return self.context.get_resource(path)



###########################################################################
# The 'ProxyNewInstance' is like 'NewInstance', it just adds the possibility
# to choose the sub-type of the resource to be added.
###########################################################################
class ProxyNewInstance(NewInstance):
    """This particular view allows to choose the resource to add from a
    collection of resource classes, with radio buttons.
    """

    template = 'base/proxy_new_instance.xml'

    type = hidden_field(source='query')


    @thingy_lazy_property
    def resource_class(self):
        type = self.type.value
        return get_resource_class(type)


    @thingy_lazy_property
    def class_title(self):
        cls = self.resource_class
        return cls.class_title.gettext()


    def items(self):
        document_types = get_document_types(self.type.value)
        if not document_types:
            return None

        # Multiple types
        if len(document_types) == 1:
            return None

        items = []
        selected = self.type.value
        items = [
            {'title': x.class_title.gettext(),
             'class_id': x.class_id,
             'selected': x.class_id == selected,
             'icon': '/ui/' + x.class_icon16}
            for x in document_types ]
        if selected is None:
            items[0]['selected'] = True

        return items


    def action(self):
        resource = self.resource
        context = self.context

        # Create the resource
        cls = get_resource_class(self.type.value)
        name = self.new_resource_name
        child = resource.make_resource(name, cls)
        # The metadata
        language = resource.get_content_language(context)
        title = Property(self.title.value, lang=language)
        child.metadata.set_property('title', title)

        context.message = messages.MSG_NEW_RESOURCE
        location = str(child.path)
        context.created(location)

