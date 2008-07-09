# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from datetime import datetime

# Import from itools
from itools.datatypes import DateTime, String, Unicode
from itools.gettext import MSG
from itools.stl import stl
from itools.web import STLForm
from itools.workflow import (Workflow, WorkflowAware as BaseWorkflowAware,
                             WorkflowError)

# Import from ikaaro
from metadata import Record


###########################################################################
# Views
###########################################################################
class StateForm(STLForm):

    access = 'is_allowed_to_edit'
    __label__ = MSG(u'State', __name__)
    title = u'Workflow State'
    icon = 'state.png'
    template = '/ui/WorkflowAware_state.xml'
    schema = {
        'transition': String(mandatory=True),
        'comments': Unicode,
    }


    def get_namespace(self, model, context):
        namespace = {}
        # State
        namespace['statename'] = model.get_statename()
        state = model.get_state()
        namespace['state'] = model.gettext(state['title'])
        # Posible transitions
        ac = model.get_access_control()
        transitions = []
        for name, trans in state.transitions.items():
            view = model.get_view(name)
            if ac.is_allowed_to_trans(context.user, model, view) is False:
                continue
            description = model.gettext(trans['description'])
            transitions.append({'name': name, 'description': description})
        namespace['transitions'] = transitions
        # Workflow history
        transitions = []
        for transition in model.get_property('wf_transition'):
            transitions.append(
                {'title': transition['name'],
                 'date': transition['date'].strftime('%Y-%m-%d %H:%M'),
                 'user': transition['user'],
                 'comments': transition['comments']})
        transitions.reverse()
        namespace['history'] = transitions

        return namespace


    def action(self, model, context, form):
        transition = form['transition']
        comments = form['comments']

        # Keep workflow history
        property = {
            'date': datetime.now(),
            'user': context.user.name,
            'name': transition,
            'comments': comments}
        model.set_property('wf_transition', property)
        # Change the state, through the itools.workflow way
        try:
            model.do_trans(transition)
        except WorkflowError, excp:
            context.message = unicode(excp.message, 'utf-8')
            return

        # Ok
        context.message = u'Transition done.'



###########################################################################
# Model
###########################################################################

# Workflow definition
workflow = Workflow()
add_state = workflow.add_state
add_trans = workflow.add_trans
# State: Private
description = u'A private document only can be reached by authorized users.'
add_state('private',
    title=MSG(u'Private', __name__),
    description=MSG(description, __name__))
# State: Pending
description = (
    u'A pending document awaits review from authorized users to be published.')
add_state('pending',
    title=MSG(u'Pending', __name__),
    description=MSG(description, __name__))
# State: Public
description = u'A public document can be reached by even anonymous users.'
add_state('public',
    title=MSG(u'Public', __name__),
    description=MSG(description, __name__))
# Transition: Publish
add_trans('publish', 'private', 'public',
    description=MSG(u'Publish the document.', __name__))
# Transition: Request
add_trans('request', 'private', 'pending',
    description=MSG(u'Request the document publication.', __name__))
# Transition: Unrequest
add_trans('unrequest', 'pending', 'private',
    description=MSG(u'Retract the document.', __name__))
# Transition: Reject
add_trans('reject', 'pending', 'private',
    description=MSG(u'Reject the document.', __name__))
# Transition: Accept
add_trans('accept', 'pending', 'public',
    description=MSG(u'Accept the document.', __name__))
# Transition: Retire
add_trans('retire', 'public', 'private',
    description=MSG(u'Retire the document.', __name__))
# Define the initial state
workflow.set_initstate('private')



class WFTransition(Record):

    schema = {
        'date': DateTime,
        'name': String,
        'user': String,
        'comments': Unicode}



class WorkflowAware(BaseWorkflowAware):

    workflow = workflow


    ########################################################################
    # Metadata
    ########################################################################
    @classmethod
    def get_metadata_schema(cls):
        return {
            'state': String,
            'wf_transition': WFTransition,
            }


    ########################################################################
    # API
    ########################################################################
    def get_workflow_state(self):
        if self.has_property('state'):
            return self.get_property('state')
        return self.workflow.initstate

    def set_workflow_state(self, value):
        self.set_property('state', value)

    workflow_state = property(get_workflow_state, set_workflow_state, None, '')


    def get_publication_date(self):
        # FIXME This method only has sense if the workflow has a 'public'
        # state with the intended meaning.
        state = self.get_property('state')
        if state != 'public':
            return None

        dates = []
        for transition in self.get_property('wf_transition'):
            date = transition.get('date')
            # Be robust
            if date is None:
                continue
            dates.append(date)

        # Be robust
        if not dates:
            return None

        dates.sort()
        return dates[-1]


    ########################################################################
    # User Interface
    ########################################################################
    edit_state = StateForm()
