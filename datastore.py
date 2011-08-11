# -*- coding: UTF-8 -*-
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

# Import from the Standard Library
from random import random

# Import from itools
from itools.gettext import MSG

# Import from ikaaro
from folder import Folder


def new_name():
    name = '%.20f' % random()
    return name[2:]



class DataStore(Folder):

    class_id = 'data-store'
    class_title = MSG(u'Data Store')

    is_content = False


    def make_resource_name(self, new_name=new_name):
        name = new_name()
        while self.get_resource(name, soft=True):
            name = new_name()
        return name
