# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
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


resources_registry = {}

def register_resource_class(resource_class, format=None):
    if format is None:
        format = resource_class.class_id
    resources_registry[format] = resource_class


def _lookup_class_id(class_id):
    if class_id in resources_registry:
        return class_id

    if '/' in class_id:
        class_id = class_id.split('/')[0]
        if class_id in resources_registry:
            return class_id

    return None


def get_resource_class(class_id):
    class_id = _lookup_class_id(class_id)
    if class_id is None:
        class_id = 'application/octet-stream'

    return resources_registry[class_id]


def register_document_type(resource_class, container_cls_id='folder'):
    container_cls = get_resource_class(container_cls_id)
    cls_register = container_cls.__dict__.get('_register_document_types')
    if cls_register and resource_class.class_id in cls_register:
        # Already registered
        return

    # Check if the resource_class is not already defined in a ancestor classes
    for i, ancestor_class in enumerate(container_cls.__mro__):
        if i == 0:
            # Skip myself
            continue
        get = ancestor_class.__dict__.get
        ancestor_register = get('_register_document_types')
        if ancestor_register is None:
            continue
        if resource_class.class_id in ancestor_register:
            # Already registered in ancestor class
            return

    # Not defined in any ancestor classes
    if cls_register is None:
        cls_register = []
        setattr(container_cls, '_register_document_types', cls_register)
    cls_register.append(resource_class.class_id)
