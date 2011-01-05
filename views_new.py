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
from itools.core import freeze
from itools.csv import Property
from itools.datatypes import String, Unicode
from itools.gettext import MSG
from itools.handlers import checkid
from itools.web import ERROR, FormError

# Import from ikaaro
from autoform import AutoForm, ReadOnlyWidget, location_widget, title_widget
from buttons import Button
from datatypes import ContainerPathDatatype
from registry import get_resource_class
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
        'path': ContainerPathDatatype,
        'name': String(default='')})
    widgets = freeze([
        ReadOnlyWidget('cls_description'),
        title_widget,
        location_widget])
    actions = [Button(access=True, css='button-ok', title=MSG(u'Add'))]
    context_menus = freeze([])
    goto_view = None


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
            return resource.get_abspath()
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
        return form['name'].strip() or form['title']


    def _get_form(self, resource, context):
        form = super(NewInstance, self)._get_form(resource, context)

        # 1. The container
        container = resource
        path = form['path']
        if path is not None:
            container = context.site_root.get_resource(path)
        ac = container.get_access_control()
        class_id = context.query['type']
        if not ac.is_allowed_to_add(context.user, container, class_id):
            path = '/' if path == '.' else '/%s/' % path
            msg = ERROR(u'Adding resources to {path} is not allowed.')
            raise FormError, msg.gettext(path=path)
        form['container'] = container

        # 2. Strip the title
        form['title'] = form['title'].strip()

        # 3. The name
        name = self.get_new_resource_name(form)
        if not name:
            raise FormError, messages.MSG_NAME_MISSING
        try:
            name = checkid(name)
        except UnicodeEncodeError:
            name = None
        if name is None:
            raise FormError, messages.MSG_BAD_NAME
        # Check the name is free
        if container.get_resource(name, soft=True) is not None:
            raise FormError, messages.MSG_NAME_CLASH
        form['name'] = name

        # Ok
        return form


    def action(self, resource, context, form):
        # Get the container
        container = form['container']
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
        if self.goto_view:
            goto = '%s/;%s' % (goto, self.goto_view)
        return context.come_back(messages.MSG_NEW_RESOURCE, goto=goto)
