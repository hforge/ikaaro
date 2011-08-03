# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2008 Nicolas Deram <nicolas@itaapy.com>
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
from itools.datatypes import Enumerate
from itools.gettext import MSG
from itools.xml import XMLParser

# Import from ikaaro
from autoform import SelectWidget
from fields import Select_Field


class State_Datatype(Enumerate):

    default = 'private'
    options = [
        {'name': 'private', 'value': MSG(u'Private')},
        {'name': 'public', 'value': MSG(u'Public')}]


class State_Widget(SelectWidget):

    title = MSG(u'State')
    datatype = State_Datatype
    has_empty_option = False


class State_Field(Select_Field):

    title = MSG(u'State')
    datatype = State_Datatype
    widget = State_Widget



class WorkflowAware(object):

    fields = ['state']
    state = State_Field(indexed=True, stored=True)



def get_workflow_preview(resource, context):
    if not isinstance(resource, WorkflowAware):
        return None
    state = resource.get_value('state')
    state_title = resource.get_value_title('state').gettext().encode('utf-8')
    # TODO Include the template in the base table
    state = '<span class="wf-%s">%s</span>' % (state, state_title)
    return XMLParser(state)
