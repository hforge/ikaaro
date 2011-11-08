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

# Import from itools
from itools.database import Resource
from itools.gettext import MSG

# Import from ikaaro
from autoform import CheckboxWidget
from datatypes import Groups_Datatype
from fields import Select_Field



class Share_Field(Select_Field):

    access = 'is_allowed_to_share'
    title = MSG(u'Share')
    datatype = Groups_Datatype
    widget = CheckboxWidget
    multiple = True
    indexed = True



class Share_Aware(Resource):

    share = Share_Field
