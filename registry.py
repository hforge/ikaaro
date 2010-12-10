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



documents_registry = []

def register_document_type(resource_class):
    documents_registry.append(resource_class)


def get_document_types():
    return documents_registry
