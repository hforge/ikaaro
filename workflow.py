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
from itools.core import freeze, thingy_lazy_property
from itools.csv import Property
from itools.datatypes import String, Unicode
from itools.gettext import MSG
from itools.http import get_context
from itools.i18n import format_datetime
from itools.log import log_error
from itools.web import STLForm, INFO, ERROR, choice_field, textarea_field
from itools.workflow import Workflow, WorkflowAware as BaseWorkflowAware
from itools.workflow import WorkflowError
from itools.xml import XMLParser



###########################################################################
# Views
###########################################################################
class StateForm(STLForm):

    access = 'is_allowed_to_edit'
    view_title = MSG(u'Publication')
    icon = 'state.png'
    template = 'WorkflowAware_state.xml'

    transition = choice_field(required=True)
    comments = textarea_field()


    def statename(self):
        return self.resource.get_statename()


    @thingy_lazy_property
    def state(self):
        return self.resource.get_state()


    def state_title(self):
        return self.state['title']


    def transitions(self):
        resource = self.resource
        user = self.context.user

        ac = resource.get_access_control()
        transitions = []
        for name, trans in self.state.transitions.items():
            view = resource.get_view(name)
            if ac.is_allowed_to_trans(user, resource, view) is False:
                continue
            description = trans['description'].gettext()
            transitions.append({'name': name, 'description': description})

        return transitions


    def history(self):
        context = self.context
        user = context.user
        workflow = self.resource.metadata.get_property('workflow')

        history = []
        if workflow is not None:
            for wf in workflow:
                history.append(
                    {'title': wf.parameters['transition'][0],
                     'date': format_datetime(wf.parameters['date']),
                     'user': context.get_user_title(wf.parameters['author']),
                     'comments': wf.value})
            history.reverse()

        return history


    def action(self, resource, context, form):
        try:
            resource.make_transition(form['transition'], form['comments'])
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
            return state.value
        return self.workflow.initstate


    def set_workflow_state(self, value):
        self.set_property('state', value)


    # XXX itools.workflow API
    workflow_state = property(get_workflow_state)


    ########################################################################
    # API
    ########################################################################
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


    def make_transition(self, transition, comments=u''):
        # Change the state, with the itools.workflow API
        self.do_trans(transition)

        # Keep comment
        user = get_context().user
        username = user and user.get_name() or None
        now = datetime.now()
        workflow = Property(comments, date=now, author=username,
                            transition=[transition])
        self.set_property('workflow', workflow)


    ########################################################################
    # User Interface
    ########################################################################
    edit_state = StateForm()


    ########################################################################
    # Update
    ########################################################################
    def update_20090122(self):
        metadata = self.metadata
        if metadata.has_property('wf_transition'):
            metadata.del_property('wf_transition')



def get_workflow_preview(resource, context):
    if not isinstance(resource, WorkflowAware):
        return None
    statename = resource.get_statename()
    state = resource.get_state()
    msg = state['title'].gettext().encode('utf-8')
    path = resource.path
    # TODO Include the template in the base table
    state = (
        '<a href="%s/;edit_state" class="workflow">'
        '<strong class="wf-%s">%s</strong></a>') % (path, statename, msg)
    return XMLParser(state)
