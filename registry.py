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


objects_registry = {}

def register_object_class(object, format=None):
    if format is None:
        format = object.class_id
    objects_registry[format] = object


def get_object_class(class_id, is_file=True):
    if class_id in objects_registry:
        return objects_registry[class_id]

    if '/' in class_id:
        class_id = class_id.split('/')[0]
        if class_id in objects_registry:
            return objects_registry[class_id]

    # Default
    if is_file:
        return objects_registry['application/octet-stream']

    return objects_registry['application/x-not-regular-file']


websites_registry = {}

def register_website(website):
    websites_registry[website.class_id] = website


def get_register_websites():
    return websites_registry.itervalues()


def get_website_class(class_id):
    return websites_registry[class_id]
