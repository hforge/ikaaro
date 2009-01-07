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

# Import from the Standard Library
from datetime import datetime

# Import from itools
from itools.datatypes import DateTime, String, Unicode
from itools.gettext import MSG
from itools.i18n import format_datetime
from itools.web import STLForm, INFO, ERROR
from itools.workflow import Workflow, WorkflowAware as BaseWorkflowAware
from itools.workflow import WorkflowError

# Import from ikaaro
from metadata import Record


###########################################################################
# Views
###########################################################################
class StateForm(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Publication')
    icon = 'state.png'
    template = '/ui/WorkflowAware_state.xml'
    schema = {
        'transition': String(mandatory=True),
        'comments': Unicode,
    }


    def get_namespace(self, resource, context):
        # State
        state = resource.get_state()
        # Posible transitions
        ac = resource.get_access_control()
        transitions = []
        for name, trans in state.transitions.items():
            view = resource.get_view(name)
            if ac.is_allowed_to_trans(context.user, resource, view) is False:
                continue
            description = trans['description'].gettext()
            transitions.append({'name': name, 'description': description})
        # Workflow history
        users = resource.get_resource('/users')
        history = []
        for transition in resource.get_property('wf_transition'):
            userid = transition['user']
            user = users.get_resource(userid)
            history.append(
                {'title': transition['name'],
                 'date': format_datetime(transition['date']),
                 'user': user.get_title(),
                 'comments': transition['comments']})
        history.reverse()

        # Ok
        return {
            'statename': resource.get_statename(),
            'state': state['title'],
            'transitions': transitions,
            'history': history,
        }


    def action(self, resource, context, form):
        transition = form['transition']
        comments = form['comments']

        # Keep workflow history
        property = {
            'date': datetime.now(),
            'user': context.user.name,
            'name': transition,
            'comments': comments}
        resource.set_property('wf_transition', property)
        # Change the state, through the itools.workflow way
        try:
            resource.do_trans(transition)
        except WorkflowError, excp:
            context.server.log_error(context)
            context.message = ERROR(unicode(excp.message, 'utf-8'))
            return

        # Ok
        context.message = INFO(u'Transition done.')



###########################################################################
# Model
###########################################################################

# Workflow definition
workflow = Workflow()
add_state = workflow.add_state
add_trans = workflow.add_trans
# State: Private
description = u'A private document only can be reached by authorized users.'
add_state('private', title=MSG(u'Private'),
    description=MSG(description))
# State: Pending
description = (
    u'A pending document awaits review from authorized users to be published.')
add_state('pending', title=MSG(u'Pending'),
    description=MSG(description))
# State: Public
description = u'A public document can be reached by even anonymous users.'
add_state('public', title=MSG(u'Public'),
    description=MSG(description))
# Transition: Publish
add_trans('publish', 'private', 'public',
    description=MSG(u'Publish the document.'))
# Transition: Request
add_trans('request', 'private', 'pending',
    description=MSG(u'Request the document publication.'))
# Transition: Unrequest
add_trans('unrequest', 'pending', 'private',
    description=MSG(u'Retract the document.'))
# Transition: Reject
add_trans('reject', 'pending', 'private',
    description=MSG(u'Reject the document.'))
# Transition: Accept
add_trans('accept', 'pending', 'public',
    description=MSG(u'Accept the document.'))
# Transition: Retire
add_trans('retire', 'public', 'private',
    description=MSG(u'Retire the document.'))
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
