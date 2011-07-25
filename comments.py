# -*- coding: UTF-8 -*-
# Copyright (C) 2010 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from re import compile
from textwrap import TextWrapper
import unicodedata

# Import from itools
from itools.datatypes import DateTime, Enumerate, Integer, String, Unicode
from itools.gettext import MSG
from itools.html import xhtml_uri
from itools.web import STLForm, STLView
from itools.xml import START_ELEMENT, END_ELEMENT, TEXT

# Import from ikaaro
from autoform import HiddenWidget, SelectWidget
from buttons import Button
from messages import MSG_CHANGES_SAVED


comment_datatype = Unicode(source='metadata', multiple=True,
                           parameters_schema={'date': DateTime,
                                              'author': String,
                                              'state': String})


url_expr = compile('([fh]t?tps?://[\w;/?:@&=+$,.#\-%]*)')
class OurWrapper(TextWrapper):

    def _split(self, text):
        # Override default's '_split' method to define URLs as unbreakable,
        # and reduce URLs if needed.
        # XXX This is fragile, since it uses TextWrapper private API.

        # Keep a mapping from reduced URL to full URL
        self.urls_map = {}

        # Get the chunks
        chunks = []
        for segment in url_expr.split(text):
            starts = segment.startswith
            if starts('http://') or starts('https://') or starts('ftp://'):
                if len(segment) > 95:
                    # Reduce URL
                    url = segment
                    segment = segment[:46] + '...' + segment[-46:]
                    self.urls_map[segment] = url
                else:
                    self.urls_map[segment] = segment
                chunks.append(segment)
            else:
                chunks.extend(TextWrapper._split(self, segment))
        return chunks


    # These two methods have been originaly wrote by
    # Matt Mackall <mpm@selenic.com> for mercurial/utils.py file.
    # http://hg.kublai.com/mercurial/main/diff/45aabc523c86/mercurial/util.py
    def _cutdown(self, string, space_left):
        l = 0
        ucstring = unicode(string, 'utf8')
        w = unicodedata.east_asian_width
        for i in xrange(len(ucstring)):
            l += w(ucstring[i]) in 'WFA' and 2 or 1
            if space_left < l:
                return (ucstring[:i].encode('utf8'),
                        ucstring[i:].encode('utf8'))
        return string, ''


    def _handle_long_word(self, reversed_chunks, cur_line, cur_len, width):
        space_left = max(width - cur_len, 1)

        if self.break_long_words:
            cut, res = self._cutdown(reversed_chunks[-1], space_left)
            cur_line.append(cut)
            reversed_chunks[-1] = res
        elif not cur_line:
            cur_line.append(reversed_chunks.pop())



def indent(text):
    """Replace URLs by HTML links.  Wrap lines (with spaces) to 95 chars.
    """
    text = text.encode('utf-8')
    # Wrap
    buffer = []
    text_wrapper = OurWrapper(width=95)
    for line in text.splitlines():
        line = text_wrapper.fill(line) + '\n'
        for segment in url_expr.split(line):
            url = text_wrapper.urls_map.get(segment)
            if url is None:
                buffer.append(segment)
            else:
                if buffer:
                    yield TEXT, ''.join(buffer), 1
                    buffer = []
                # <a>...</a>
                attributes = {(None, 'href'): url}
                yield START_ELEMENT, (xhtml_uri, 'a', attributes), 1
                yield TEXT, segment, 1
                yield END_ELEMENT, (xhtml_uri, 'a'), 1
    if buffer:
        yield TEXT, ''.join(buffer), 1
        buffer = []



class CommentView(STLView):
    template = '/ui/comment_view.xml'
    comment_columns = ('user', 'datetime', 'comment', 'workflow', 'index')
    # Configuration
    comment = None
    comment_index = None
    edit_mode = False


    def get_comment_columns(self, resource, context):
        return self.comment_columns


    def get_item_value(self, resource, context, item, column):
        if column == 'user':
            return context.root.get_user_title(item.get_parameter('author'))
        elif column == 'datetime':
            return context.format_datetime(item.get_parameter('date'))
        elif column == 'comment':
            return indent(item.value)
        elif column == 'workflow':
            datatype = resource.comment_workflow
            if self.edit_mode is False or datatype is None:
                return None
            state = item.get_parameter('state', datatype.get_default())
            widget = SelectWidget('state', datatype=datatype, value=state,
                                  has_empty_option=False)
            return widget
        elif column == 'index':
            if self.edit_mode is False:
                return None
            widget = HiddenWidget('index', value=self.comment_index)
            return widget
        raise ValueError, 'unexpected "%s" column' % column


    def get_comment_value(self, resource, context, column):
        item = self.comment
        return self.get_item_value(resource, context, item, column)


    def get_namespace(self, resource, context):
        namespace = {'number': self.comment_index}
        columns = self.get_comment_columns(resource, context)

        for key in columns:
            namespace[key] = self.get_comment_value(resource, context, key)

        return namespace



class CommentsView(STLForm):
    template = '/ui/comments.xml'
    schema = {
        'state': String(multiple=True),
        'index': Integer(multiple=True)}
    query_schema = {'filter': String()}
    edit_mode = False


    def get_namespace(self, resource, context):
        # Filter
        workflow_datatype = resource.comment_workflow
        if workflow_datatype is None:
            filter_widget = None
            filter_comment = None
        else:
            filter_state = context.get_query_value('filter')
            filter_widget = SelectWidget('filter',
                    datatype=workflow_datatype,
                    value=filter_state, has_empty_option=True)
            default_state = workflow_datatype.get_default()
            def filter_comment(x):
                if not filter_state:
                    return False
                state = x.get_parameter('state', default_state)
                return state != filter_state

        # Comments
        _comments = resource.metadata.get_property('comment') or []
        comments = []
        comment_view = resource.comment_view
        user = context.user

        for i, comment in enumerate(_comments):
            if resource.is_allowed_to_view_comment(user, comment) is False:
                continue
            if filter_comment and filter_comment(comment):
                continue
            view = comment_view(comment=comment, comment_index=i,
                                edit_mode=self.edit_mode)
            comments.append(view.GET(resource, context))
        comments.reverse()

        namespace = {}
        namespace['edit_mode'] = self.edit_mode
        namespace['action'] = None
        namespace['actions'] = [Button(access='is_allowed_to_edit',
            title=u'Change state', resource=resource, context=context,
            name='update')]
        namespace['comments'] = comments
        namespace['filter'] = filter_widget

        return namespace


    def action_update(self, resource, context, form):
        comments = resource.metadata.get_property('comment') or []
        states = form['state']
        for i, comment_index in enumerate(form['index']):
            new_state = states[i]
            comment = comments[comment_index]
            comment.set_parameter('state', new_state)

        resource.del_property('comment')
        resource.set_property('comment', comments)
        context.message = MSG_CHANGES_SAVED



class CommentWorkflow(Enumerate):
    default = 'private'
    options = [
            {'name': 'public', 'value': u'Public'},
            {'name': 'private', 'value': u'Private'},
            {'name': 'pending', 'value': u'Pending'}]



class CommentsAware(object):
    """ - Add "comment" to class_schema.
        - Define a default workflow to be overwritten if necessary, as an
          Enumerate until now.
        - Define a default view to display a comment ("comment_view").
        - Add comments view which displays comments on edit_mode, so that you
          can filter by workflow state and change state on any comment(s).
        - Method "is_allowed_to_view_comment" can be overwritten to define
          access to comments on specific criteria.
    """
    class_schema = {'comment': comment_datatype}

    comment_workflow = CommentWorkflow

    comments = CommentsView(access='is_allowed_to_edit', edit_mode=True)
    comment_view = CommentView


    def is_allowed_to_view_comment(self, user, comment):
        return True


    def get_comments(self, state=None):
        """ Get any comment matching given state.
            state may be a string, a tuple or a list.
        """
        if state is None:
            return list(self.get_property('comment'))

        if not isinstance(state, (tuple, list)):
            state = [state]

        comments = []
        for comment in self.metadata.get_property('comment'):
            if comment.get_parameter('state') in state:
                comments.append(comment)
        return comments
