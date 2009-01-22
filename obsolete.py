# -*- coding: UTF-8 -*-
# Copyright (C) 2009 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from itools.datatypes import DataType, String


###########################################################################
# XXX Backwards compatibility with 0.50
###########################################################################
class Record(DataType):

    # Set your own default list to avoid sharing this instance
    default = freeze([])
    schema = {}

    multiple = True



class History(Record):
    schema = {
        'date': String,
        'user': String,
        'size': String}


class WFTransition(Record):
    schema = {
        'date': String,
        'name': String,
        'user': String,
        'comments': String}


