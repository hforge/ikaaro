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
from itools.web import STLView, STLForm

# Import from ikaaro
from registry import get_object_class


"""This module contains some generic views used by different objects.
"""


class IconsView(STLView):
    """This view draws a menu where each menu item is made up of a big
    icon (48x48 pixels), a title and a description.
    """

    template = '/ui/generic/icons_view.xml.en'

    def get_namespace(self, model, context):
        """TODO Write a docstring explaining the expected namespace.
        """
        raise NotImplementedError



class NewInstanceForm(STLForm):
    """This is the base class for all ikaaro forms meant to create and
    add a new object to the database.
    """

    def title(self, **kw):
        type = kw.get('type')
        cls = get_object_class(type)
        if cls is not None:
            return cls.class_title
        # Default
        return 'Unknown object.'


    def icon(self, model, **kw):
        type = kw.get('type')
        cls = get_object_class(type)
        if cls is not None:
            return cls.get_class_icon()
        # Default
        return '/ui/icons/16x16/new.png'




class BrowseForm(STLForm):

    template = '/ui/generic/browse.xml'
