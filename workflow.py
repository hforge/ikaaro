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
from itools.core import freeze
from itools.datatypes import Enumerate, String, Unicode
from itools.gettext import MSG
from itools.log import log_error
from itools.web import INFO, ERROR
from itools.workflow import Workflow, WorkflowAware as BaseWorkflowAware
from itools.workflow import WorkflowError
from itools.xml import XMLParser

# Import from ikaaro
from autoform import AutoForm, SelectWidget



class StateEnumerate(Enumerate):

    default = ''

    def get_options(self):
        resource = self.resource
        states = resource.workflow.states
        state = resource.get_state()

        ac = resource.get_access_control()
        user = self.context.user
        options = [
            {'name': name, 'value': states[trans.state_to].metadata['title']}
            for name, trans in state.transitions.items()
            if ac.is_allowed_to_trans(user, resource, name) ]
        options.append({'name': '', 'value': state.metadata['title']})
        options.sort(key=lambda x: x['value'])
        return options



class StateForm(AutoForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Publication')
    icon = 'state.png'

    def get_schema(self, resource, context):
        return {'state': StateEnumerate(resource=resource, context=context)}

    widgets = [
        SelectWidget('state', title=MSG(u'State'), has_empty_option=False)]


    def action(self, resource, context, form):
        transition = form['state']
        if transition == '':
            context.message = INFO(u'Nothing to do.')
            return

        try:
            resource.do_trans(transition)
        except WorkflowError, excp:
            log_error('Transition failed', domain='ikaaro')
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



class WorkflowAware(BaseWorkflowAware):

    class_version = '20090122'
    workflow = workflow


    from obsolete.metadata import WFTransition
    class_schema = freeze({
        # Metadata
        'state': String(source='metadata'),
        'workflow': Unicode(source='metadata', multiple=True),
        # Metadata (XXX backwards compatibility with 0.50)
        'wf_transition': WFTransition(source='metadata'),
        # Other
        'workflow_state': String(stored=True, indexed=True),
        })


    def get_workflow_state(self):
        state = self.get_property('state')
        if state:
            return state
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

        workflow = self.get_property('workflow')
        if not workflow:
            return None
        return workflow[-1].parameters['date']


    # Views
    edit_state = StateForm()



def get_workflow_preview(resource, context):
    if not isinstance(resource, WorkflowAware):
        return None
    statename = resource.get_statename()
    state = resource.get_state()
    msg = state['title'].gettext().encode('utf-8')
    path = context.get_link(resource)
    # TODO Include the template in the base table
    state = ('<a href="%s/;edit_state" class="workflow">'
             '<strong class="wf-%s">%s</strong>'
             '</a>') % (path, statename, msg)
    return XMLParser(state)
