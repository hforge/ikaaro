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

# Import from itools
from itools.core import freeze, merge_dicts
from itools.csv import Property
from itools.datatypes import String, Unicode
from itools.gettext import MSG
from itools.handlers import checkid
from itools.web import FormError

# Import from ikaaro
from autoform import AutoForm
from autoform import ReadOnlyWidget, SelectWidget, TextWidget, title_widget
from buttons import Button
from registry import get_resource_class, get_document_types
import messages



class NewInstance(AutoForm):
    """This is the base class for all ikaaro forms meant to create and
    add a new resource to the database.
    """

    access = 'is_allowed_to_add'
    query_schema = freeze({
        'type': String,
        'title': Unicode,
        'path': String,
        'name': String})
    schema = freeze({
        'cls_description': Unicode,
        'title': Unicode,
        'path': String(mandatory=True),
        'name': String})
    widgets = freeze([
        ReadOnlyWidget('cls_description'),
        title_widget,
        SelectWidget('path', title=MSG(u'Path'), has_empty_option=False),
        TextWidget('name', title=MSG(u'Name'), default='')])
    actions = [Button(access=True, css='button-ok', title=MSG(u'Add'))]
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
        if name == 'cls_description':
            class_id = context.query['type']
            cls = get_resource_class(class_id)
            return cls.class_description.gettext()
        elif name == 'path':
            class_id = context.query['type']
            resource_path = resource.get_abspath()

            cache = {}
            items = []
            selected, selected_len = 0, 0
            idx = 0
            for brain in context.root.search(is_folder=True).get_documents():
                if brain.format not in cache:
                    resource = context.root.get_resource(brain.abspath)
                    if not resource.is_content_container():
                        continue
                    for cls in resource.get_document_types():
                        if cls.class_id == class_id:
                            cache[brain.format] = True
                            break
                    else:
                        cache[brain.format] = False

                if not cache[brain.format]:
                    continue

                path = context.site_root.get_pathto(brain)
                title = '/' if not path else ('/%s' % path)
                # Selected
                if context.query['path'] == path:
                    selected, selected_len = idx, -1
                elif selected_len > -1:
                    prefix = resource_path.get_prefix(brain.abspath)
                    prefix_len = len(prefix)
                    if prefix_len > selected_len:
                        selected, selected_len = idx, prefix_len
                # Next
                items.append({'name': path, 'value': title, 'selected': False})
                idx += 1

            items[selected]['selected'] = True
            return items
        elif name in self.get_query_schema():
            return context.query[name]
        return AutoForm.get_value(self, resource, context, name, datatype)


    def icon(self, resource, **kw):
        type = kw.get('type')
        cls = get_resource_class(type)
        if cls is not None:
            return cls.get_class_icon()
        # Default
        return 'new.png'


    def get_new_resource_name(self, form):
        # If the name is not explicitly given, use the title
        return form['name'] or form['title']


    def _get_form(self, resource, context):
        form = super(NewInstance, self)._get_form(resource, context)

        # 1. Strip title and name
        form['title'] = form['title'].strip()
        form['name'] = form['name'].strip()

        # 2. Get the name
        name = self.get_new_resource_name(form)
        if not name:
            raise FormError, messages.MSG_NAME_MISSING
        try:
            name = checkid(name)
        except UnicodeEncodeError:
            name = None
        if name is None:
            raise FormError, messages.MSG_BAD_NAME

        # 3. Check the name is free
        if resource.get_resource(name, soft=True) is not None:
            raise FormError, messages.MSG_NAME_CLASH
        form['name'] = name

        # Ok
        return form


    def action(self, resource, context, form):
        # Get the container
        container = context.site_root.get_resource(form['path'])
        # Make the resource
        class_id = context.query['type']
        cls = get_resource_class(class_id)
        child = container.make_resource(form['name'], cls)
        # Set properties
        language = container.get_edit_languages(context)[0]
        title = Property(form['title'], lang=language)
        child.metadata.set_property('title', title)
        # Ok
        goto = str(resource.get_pathto(child))
        return context.come_back(messages.MSG_NEW_RESOURCE, goto=goto)



subtype_widget = SelectWidget('class_id', title=MSG(u'Subtype'),
                              has_empty_option=False)
class ProxyNewInstance(NewInstance):
    """This particular view allows to choose the resource to add from a
    collection of resource classes, with radio buttons.
    """

    schema = merge_dicts(NewInstance.schema, class_id=String(madatory=True))


    def get_widgets(self, resource, context):
        widgets = NewInstance.widgets

        type = context.query['type']
        cls = get_resource_class(type)
        document_types = get_document_types(type)
        if len(document_types) < 2:
            return widgets

        return widgets + [subtype_widget]


    def get_value(self, resource, context, name, datatype):
        if name == 'class_id':
            type = context.query['type']
            cls = get_resource_class(type)
            document_types = get_document_types(type)
            selected = context.get_form_value('class_id')
            items = [
                {'name': x.class_id,
                 'value': x.class_title.gettext(),
                 'selected': x.class_id == selected}
                for x in document_types ]
            if selected is None:
                items[0]['selected'] = True

            # Ok
            return items

        proxy = super(ProxyNewInstance, self)
        return proxy.get_value(resource, context, name, datatype)


    def action(self, resource, context, form):
        # Get the container
        container = context.site_root.get_resource(form['path'])
        # Make the resource
        class_id = form['class_id'] or context.query['type']
        cls = get_resource_class(class_id)
        child = container.make_resource(form['name'], cls)
        # Set properties
        language = container.get_edit_languages(context)[0]
        title = Property(form['title'], lang=language)
        child.metadata.set_property('title', title)
        # Ok
        goto = str(resource.get_pathto(child))
        return context.come_back(messages.MSG_NEW_RESOURCE, goto=goto)
