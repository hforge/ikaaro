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
from itools.datatypes import String, Unicode
from itools.gettext import MSG
from itools.i18n import format_datetime
from itools.log import log_error
from itools.web import STLForm, INFO, ERROR, get_context
from itools.workflow import Workflow, WorkflowAware as BaseWorkflowAware
from itools.workflow import WorkflowError
from itools.xml import XMLParser



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
        root = context.root
        user = context.user
        # State
        state = resource.get_state()
        # Posible transitions
        ac = resource.get_access_control()
        transitions = []
        for name, trans in state.transitions.items():
            view = resource.get_view(name)
            if ac.is_allowed_to_trans(user, resource, view) is False:
                continue
            description = trans['description'].gettext()
            transitions.append({'name': name, 'description': description})
        # Workflow history
        history = []
        for revision in resource.get_revisions():
            transition, comment = parse_git_message(revision['message'])
            if transition is not None:
                history.append(
                    {'title': transition,
                     'date': format_datetime(revision['date']),
                     'user': root.get_user_title(revision['username']),
                     'comments': comment})
        history.reverse()

        # Ok
        return {
            'statename': resource.get_statename(),
            'state': state['title'],
            'transitions': transitions,
            'history': history,
        }


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



def parse_git_message(message):
    """Parses a git message of the form:

      edit state: <transition>

      <comment>

    Returns a tuple with the transition and comment.
    """
    n = len('edit state: ')
    if message[:n] != 'edit state: ':
        return None, None

    m = message.find('\n')
    # No comment
    if m == -1:
        return message[n:], u''
    # With comment
    return message[n:m], unicode(message[m+2:], 'utf-8')



class WorkflowAware(BaseWorkflowAware):

    class_version = '20090122'
    workflow = workflow


    ########################################################################
    # Metadata
    ########################################################################
    @classmethod
    def get_metadata_schema(cls):
        from obsolete.metadata import WFTransition
        return {
            'state': String,
            # XXX Backwards compatibility with 0.50
            'wf_transition': WFTransition,
            }


    ########################################################################
    # API
    ########################################################################
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

        for revision in self.get_revisions():
            if revision['message'].startswith('edit state: '):
                return revision['committer'][1]

        return None


    def make_transition(self, transition, comments=u''):
        # Change the state, with the itools.workflow API
        self.do_trans(transition)

        # Keep workflow history
        if comments:
            git_message = u'edit state: %s\n\n%s' % (transition, comments)
        else:
            git_message = u'edit state: %s' % transition
        context = get_context()
        context.git_message = git_message


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
    # Apply ACL
    ac = resource.get_access_control()
    if ac.is_allowed_to_edit(context.user, resource):
        path = context.get_link(resource)
        state = ('<a href="%s/;edit_state" class="workflow">'
                 '<strong class="wf-%s">%s</strong>'
                 '</a>') % (path, statename, msg)
    else:
        state = '<strong class="wf-%s">%s</strong>' % (statename, msg)
    return XMLParser(state)
