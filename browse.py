# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2007 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
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
from itools.datatypes import Boolean, Integer, String, Unicode
from itools.gettext import MSG
from itools.stl import stl
from itools.xapian import EqQuery, AndQuery, PhraseQuery

# Import from ikaaro
from messages import *
from views import BrowseForm


class BrowseContent(BrowseForm):

    access = 'is_allowed_to_view'
    access_POST = 'is_allowed_to_edit'
    title = MSG(u'Browse Content')
    icon = 'folder.png'

    schema = {
        'ids': String(multiple=True, mandatory=True),
    }

    search_fields =  [
        ('title', MSG(u'Title')),
        ('text', MSG(u'Text')),
        ('name', MSG(u'Name')),
    ]

    query_schema = {
        'search_field': String,
        'search_term': Unicode,
        'search_subfolders': Boolean(default=False),
        'sortorder': String(default='up'),
        'sortby': String(multiple=True, default=['title']),
        'batchstart': Integer(default=0),
    }


    #######################################################################
    # Search form
    def search_form(self, resource, context):
        # Get values from the query
        query = context.query
        field = query['search_field']
        term = query['search_term']

        # Build the namespace
        search_fields = [
            {'name': name, 'title': title,
             'selected': name == field}
            for name, title in self.search_fields ]
        namespace = {
            'search_term': term,
            'search_fields': search_fields,
            # NOTE Folder's content specifics
            'search_subfolders': query['search_subfolders'],
        }

        # Ok
        template = resource.get_resource('/ui/folder/browse_search.xml')
        return stl(template, namespace)


    def search(self, resource, context, *args):
        # Get the parameters from the query
        query = context.query
        search_term = query['search_term'].strip()
        field = query['search_field']
        search_subfolders = query['search_subfolders']

        # Build the query
        args = list(args)
        abspath = str(resource.get_canonical_path())
        if search_subfolders is True:
            args.append(EqQuery('paths', abspath))
        else:
            args.append(EqQuery('parent_path', abspath))

        if search_term:
            args.append(PhraseQuery(field, search_term))

        if len(args) == 1:
            query = args[0]
        else:
            query = AndQuery(*args)

        return context.root.search(query)


    #######################################################################
    # Table
    columns = [
        ('name', MSG(u'Name')),
        ('title', MSG(u'Title')),
        ('format', MSG(u'Type')),
        ('mtime', MSG(u'Last Modified')),
        ('last_author', MSG(u'Last Author')),
        ('size', MSG(u'Size')),
        ('workflow_state', MSG(u'State'))]


    def get_actions(self, resource, context, results):
        # Access Control
        ac = resource.get_access_control()
        if not ac.is_allowed_to_edit(context.user, resource):
            return []

        # Return
        actions = []
        if results.get_n_documents():
            message = MSG_DELETE_SELECTION.gettext()
            actions = [
                ('remove', MSG(u'Remove'), 'button_delete',
                 'return confirmation("%s");' % message.encode('utf_8')),
                ('rename', MSG(u'Rename'), 'button_rename', None),
                ('copy', MSG(u'Copy'), 'button_copy', None),
                ('cut', MSG(u'Cut'), 'button_cut', None)]
        # Paste
        if context.has_cookie('ikaaro_cp'):
            actions.append(('paste', MSG(u'Paste'), 'button_paste', None))

        return actions


    def get_rows(self, resource, context, results):
        query = context.query
        start = query['batchstart']
        size = self.batchsize
        sortby = query['sortby']
        sortorder = query['sortorder']

        # Get the documents
        reverse = (sortorder == 'down')
        documents = results.get_documents(sort_by=sortby, reverse=reverse,
                                          start=start, size=size)

        # Get the objects, check security
        user = context.user
        root = context.root
        objects = []
        for document in documents:
            object = root.get_resource(document.abspath)
            ac = object.get_access_control()
            if ac.is_allowed_to_view(user, object):
                objects.append(object)

        # Get the object for the visible documents and extracts values
        return [ resource._browse_namespace(x, 16) for x in objects ]


    #######################################################################
    # Form Actions
    #######################################################################
    def action_remove(self, resource, context, form):
        ids = form['ids']

        # Clean the copy cookie if needed
        cut, paths = context.get_cookie('ikaaro_cp', type=CopyCookie)

        # Remove objects
        removed = []
        not_removed = []
        user = context.user
        abspath = resource.get_abspath()

        # We sort and reverse ids in order to
        # remove the childs then their parents
        ids.sort()
        ids.reverse()
        for name in ids:
            object = resource.get_resource(name)
            ac = object.get_access_control()
            if ac.is_allowed_to_remove(user, object):
                # Remove object
                try:
                    resource.del_resource(name)
                except ConsistencyError:
                    not_removed.append(name)
                    continue
                removed.append(name)
                # Clean cookie
                if str(abspath.resolve2(name)) in paths:
                    context.del_cookie('ikaaro_cp')
                    paths = []
            else:
                not_removed.append(name)

        if removed:
            objects = ', '.join(removed)
            context.message = MSG_OBJECTS_REMOVED.gettext(objects=objects)
        else:
            context.message = MSG_NONE_REMOVED


    def action_rename(self, resource, context, form):
        ids = form['ids']
        # Filter names which the authenticated user is not allowed to move
        ac = resource.get_access_control()
        user = context.user
        paths = [ x for x in ids
                  if ac.is_allowed_to_move(user, resource.get_resource(x)) ]

        # Check input data
        if not paths:
            context.message = MSG(u'No objects selected.')
            return

        # FIXME Hack to get rename working. The current user interface forces
        # the rename_form to be called as a form action, hence with the POST
        # method, but it should be a GET method. Maybe it will be solved after
        # the needed folder browse overhaul.
        ids_list = '&'.join([ 'ids=%s' % x for x in paths ])
        return get_reference(';rename?%s' % ids_list)


    def action_copy(self, resource, context, form):
        ids = form['ids']
        # Filter names which the authenticated user is not allowed to copy
        ac = resource.get_access_control()
        user = context.user
        names = [ x for x in ids
                  if ac.is_allowed_to_copy(user, resource.get_resource(x)) ]

        # Check input data
        if not names:
            message = MSG(u'No objects selected.')
            return

        abspath = resource.get_abspath()
        cp = (False, [ str(abspath.resolve2(x)) for x in names ])
        cp = CopyCookie.encode(cp)
        context.set_cookie('ikaaro_cp', cp, path='/')
        # Ok
        context.message = MSG(u'Objects copied.')


    def action_cut(self, resource, context, form):
        ids = form['ids']
        # Filter names which the authenticated user is not allowed to move
        ac = resource.get_access_control()
        user = context.user
        names = [ x for x in ids
                  if ac.is_allowed_to_move(user, resource.get_resource(x)) ]

        # Check input data
        if not names:
            message = MSG(u'No objects selected.')
            return

        abspath = resource.get_abspath()
        cp = (True, [ str(abspath.resolve2(x)) for x in names ])
        cp = CopyCookie.encode(cp)
        context.set_cookie('ikaaro_cp', cp, path='/')

        context.message = MSG(u'Objects cut.')


    action_paste_schema = {}
    def action_paste(self, resource, context, form):
        # Check there is something to paste
        cut, paths = context.get_cookie('ikaaro_cp', type=CopyCookie)
        if len(paths) == 0:
            context.message = MSG(u'Nothing to paste.')
            return

        # Paste
        target = resource
        allowed_types = tuple(target.get_document_types())
        for path in paths:
            # Check the resource actually exists
            try:
                resource = target.get_resource(path)
            except LookupError:
                continue
            if not isinstance(resource, allowed_types):
                continue

            # If cut&paste in the same place, do nothing
            if cut is True:
                source = resource.parent
                if target.get_canonical_path() == source.get_canonical_path():
                    continue

            name = generate_name(resource.name, target.get_names(), '_copy_')
            if cut is True:
                # Cut&Paste
                target.move_resource(path, name)
            else:
                # Copy&Paste
                target.copy_resource(path, name)
                # Fix state
                resource = target.get_resource(name)
                if isinstance(resource, WorkflowAware):
                    metadata = resource.metadata
                    metadata.set_property('state', resource.workflow.initstate)

        # Cut, clean cookie
        if cut is True:
            context.del_cookie('ikaaro_cp')

        context.message = MSG(u'Objects pasted.')



