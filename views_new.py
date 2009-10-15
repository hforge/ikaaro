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
from urllib import quote

# Import from itools
from itools.core import freeze, merge_dicts
from itools.csv import Property
from itools.datatypes import Date, String, Unicode, Enumerate
from itools.gettext import MSG
from itools.handlers import checkid
from itools.http import get_context
from itools.web import FormError

# Import from ikaaro
from autoform import AutoForm, DateWidget, RadioWidget, TextWidget
from autoform import name_widget, title_widget
import messages
from registry import get_resource_class, get_document_types
from views import ContextMenu



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
    query_schema = freeze({
        'type': String,
        'title': Unicode,
        'date': TodayDataType})
    schema = freeze({
        'title': Unicode,
        'date': TodayDataType(mandatory=True)})
    widgets = freeze([
        title_widget,
        DateWidget('date', title=MSG(u'Date'))])
    submit_value = MSG(u'Add')
    context_menus = freeze([])


    def get_title(self, context):
        if self.title is not None:
            return self.title
        type = context.query['type']
        if not type:
            return MSG(u'Add resource').gettext()
        cls = get_resource_class(type)
        class_title = cls.class_title.gettext()
        title = MSG(u'Add {class_title}')
        return title.gettext(class_title=class_title)


    def get_value(self, resource, context, name, datatype):
        if name in self.get_query_schema():
            value = context.get_query_value(name)
            if value is not None:
                return value
        return AutoForm.get_value(self, resource, context, name, datatype)


    def icon(self, resource, **kw):
        type = kw.get('type')
        cls = get_resource_class(type)
        if cls is not None:
            return cls.get_class_icon()
        # Default
        return 'new.png'


    def get_new_resource_name(self, form):
        return form['title'].strip()


    def _get_form(self, resource, context):
        form = AutoForm._get_form(self, resource, context)
        name = self.get_new_resource_name(form)

        # Check the name
        if not name:
            raise FormError, messages.MSG_NAME_MISSING

        try:
            name = checkid(name)
        except UnicodeEncodeError:
            name = None

        if name is None:
            raise FormError, messages.MSG_BAD_NAME

        # Check the name is free
        if resource.get_resource(name, soft=True) is not None:
            raise FormError, messages.MSG_NAME_CLASH

        # Ok
        form['name'] = name
        return form


    def get_date(self, context, form):
        return form['date']


    def get_container(self, context, form):
        from folder import Folder

        # The path of the container
        date = self.get_date(context, form)
        path = ['%04d' % date.year, '%02d' % date.month, '%02d' % date.day]

        # Get the container, create it if needed
        container = context.site_root
        for name in path:
            folder = container.get_resource(name, soft=True)
            if folder is None:
                folder = container.make_resource(name, Folder)
            container = folder

        return container


    def get_resource_class(self, context, form):
        class_id = context.query['type']
        return get_resource_class(class_id)


    def modify_resource(self, resource, context, form, child):
        title = form['title']
        language = resource.get_content_language(context)
        title = Property(title, lang=language)
        child.metadata.set_property('title', title)


    def action(self, resource, context, form):
        # 1. Get the container
        container = self.get_container(context, form)

        # 2. Make the resource
        cls = self.get_resource_class(context, form)
        child = container.make_resource(form['name'], cls)

        # 3. Edit the resource
        self.modify_resource(resource, context, form, child)

        # 4. Ok
        context.message = messages.MSG_NEW_RESOURCE
        location = str(child.path)
        context.created(location)



###########################################################################
# The 'NewInstance' view adds a resource to a folder explicitely selected
# in the form.
###########################################################################

class PathEnumerate(Enumerate):

    def get_options(cls):
        # Search
        brains = get_context().search(is_folder=True)

        # The namespace
        options = []
        for resource in brains.get_documents():
            path = str(resource.path)
            options.append({'name': path, 'value': path})
        options.sort(key=itemgetter('value'))

        # Ok
        return options


    def get_default(cls):
        resource = cls.resource
        default = resource.get_abspath()
        return str(default)


class NewInstance(NewInstanceByDate):

    query_schema = freeze({
        'type': String,
        'name': String,
        'title': Unicode})
    schema = freeze({
        'name': String,
        'title': Unicode})
    widgets = freeze([
        title_widget,
        name_widget,
        RadioWidget('path', title=MSG(u'Path'), has_empty_option=False)])


    def get_schema(self, resource, context):
        return merge_dicts(self.schema, path=PathEnumerate(resource=resource))


    def get_new_resource_name(self, form):
        # If the name is not explicitly given, use the title
        name = form['name']
        title = form['title'].strip()
        if name is None:
            return title
        return name or title


    def get_container(self, context, form):
        path = form['path']
        return context.get_resource(path)



###########################################################################
# The 'ProxyNewInstance' is like 'NewInstance', it just adds the possibility
# to choose the sub-type of the resource to be added.
###########################################################################
class ProxyNewInstance(NewInstance):
    """This particular view allows to choose the resource to add from a
    collection of resource classes, with radio buttons.
    """

    template = 'base/proxy_new_instance.xml'
    schema = {
        'name': String,
        'title': Unicode,
        'class_id': String}


    def get_namespace(self, resource, context):
        type = context.query['type']
        cls = get_resource_class(type)

        document_types = get_document_types(type)
        items = []
        if document_types:
            # Multiple types
            if len(document_types) == 1:
                items = None
            else:
                selected = context.get_form_value('class_id')
                items = [
                    {'title': x.class_title.gettext(),
                     'class_id': x.class_id,
                     'selected': x.class_id == selected,
                     'icon': '/ui/' + x.class_icon16}
                    for x in document_types ]
                if selected is None:
                    items[0]['selected'] = True
        # Ok
        return {
            'class_id': cls.class_id,
            'class_title': cls.class_title.gettext(),
            'items': items}


    def action(self, resource, context, form):
        name = form['name']
        title = form['title']

        # Create the resource
        class_id = form['class_id']
        if class_id is None:
            # Get it from the query
            class_id = context.query['type']
        cls = get_resource_class(class_id)
        child = resource.make_resource(name, cls)
        # The metadata
        language = resource.get_content_language(context)
        title = Property(title, lang=language)
        child.metadata.set_property('title', title)

        context.message = messages.MSG_NEW_RESOURCE
        location = str(child.path)
        context.created(location)

