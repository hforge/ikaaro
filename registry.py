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


def get_resource_class(class_id, is_file=True):
    if class_id in resources_registry:
        return resources_registry[class_id]

    if '/' in class_id:
        class_id = class_id.split('/')[0]
        if class_id in resources_registry:
            return resources_registry[class_id]

    # Default
    if is_file:
        return resources_registry['application/octet-stream']

    return resources_registry['application/x-not-regular-file']



documents_registry = {}

def register_document_type(resource_class, type=None):
    if not type in documents_registry:
        documents_registry[type] = []
    documents_registry[type].append(resource_class)


def get_document_types(type=None, default=None):
    return documents_registry.get(type, default)



fields_registry = {}

def register_field(name, field_cls):
    if name in fields_registry:
        raise ValueError, ('You have already register a field with this name '
                           '"%s"') % name
    fields_registry[name] = field_cls


def get_register_fields():
    return fields_registry

