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
from itools.database import Resource
from itools.datatypes import Integer, String
from itools.gettext import MSG
from itools.html import xhtml_uri
from itools.web import STLView, get_context
from itools.xml import START_ELEMENT, END_ELEMENT, TEXT

# Import from ikaaro
from autoform import HiddenWidget, SelectWidget
from buttons import Button
from fields import Select_Field, Owner_Field
from messages import MSG_CHANGES_SAVED
from resource_ import DBResource


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



def indent(text, width=95):
    """Replace URLs by HTML links.  Wrap lines (with spaces) to 95 chars.
    """
    text = text.encode('utf-8')
    # Wrap
    buffer = []
    text_wrapper = OurWrapper(width=width)
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



class Comment_View(STLView):

    template = '/ui/comment_view.xml'
    comment_columns = ('user', 'datetime', 'comment', 'workflow', 'index')
    # Configuration
    comment_index = None
    edit_mode = False
    width = 95


    def get_comment_columns(self, resource, context):
        return self.comment_columns


    def get_item_value(self, resource, context, item, column):
        if column == 'user':
            return context.root.get_user_title(item.get_value('last_author'))
        elif column == 'datetime':
            return context.format_datetime(item.get_value('mtime'))
        elif column == 'comment':
            comment = item.get_value('description')
            return indent(comment, self.width)
        elif column == 'workflow':
            datatype = item.comment_state.get_datatype()
            if self.edit_mode is False or datatype is None:
                return None
            state = item.get_value('comment_state', datatype.get_default())
            widget = SelectWidget('state', datatype=datatype, value=state,
                                  has_empty_option=False)
            return widget
        elif column == 'index':
            if self.edit_mode is False:
                return None
            widget = HiddenWidget('index', value=self.comment_index)
            return widget
        raise ValueError, 'unexpected "%s" column' % column


    def get_namespace(self, resource, context):
        namespace = {'number': self.comment_index}
        columns = self.get_comment_columns(resource, context)

        for key in columns:
            item = self.comment
            namespace[key] = self.get_item_value(resource, context, item, key)

        return namespace



class CommentState_Field(Select_Field):

    default = 'open'
    options = [
        {'name': 'open', 'value': MSG(u'Open')},
        {'name': 'archived', 'value': MSG(u'Archived')}]

    indexed = True
    stored = True


class Comment(DBResource):

    class_id = 'comment'
    class_title = MSG(u'Comment')

    # Fields
    title = None
    subject = None
    owner = Owner_Field
    comment_state = CommentState_Field

    # Sharing is acquired from container
    share = None
    def get_share(self):
        return self.parent.get_share()

    # Views
    view = Comment_View


###########################################################################
# Comment Aware (base class)
###########################################################################
class CommentsView(STLView):

    template = '/ui/comments.xml'
    schema = {
        'comment_state': String(multiple=True),
        'index': Integer(multiple=True)}
    query_schema = {'filter': String()}
    edit_mode = False


    def get_namespace(self, resource, context):
        # Filter
        field = Comment.comment_state
        datatype = field.get_datatype()
        filter_state = context.get_query_value('filter')
        filter_widget = field.widget('filter', datatype=datatype,
                                     value=filter_state,
                                     has_empty_option=True)
        default_state = datatype.get_default()
        def filter_comment(x):
            if not filter_state:
                return False
            return x.get_value('comment_state', default_state) != filter_state

        # Comments
        i = 0
        comments = []
        for comment in resource.get_comments():
            if filter_comment and filter_comment(comment):
                continue
            view = comment.view(comment=comment, comment_index=i,
                                edit_mode=self.edit_mode)
            comments.insert(0, view.GET(resource, context))
            i += 1

        button = Button(access='is_allowed_to_edit', title=MSG(u'Change state'),
                        resource=resource, context=context, name='update')
        return {
            'edit_mode': self.edit_mode,
            'action': None,
            'actions': [button],
            'comments': comments,
            'filter': filter_widget}


    def action_update(self, resource, context, form):
        comments = resource.get_property('comment')
        states = form['comment_state']
        for i, comment_index in enumerate(form['index']):
            new_state = states[i]
            comment = comments[comment_index]
            comment.set_parameter('comment_state', new_state)

        resource.del_property('comment')
        resource.set_property('comment', comments)
        context.message = MSG_CHANGES_SAVED



class CommentsAware(Resource):
    """ - Add "comment" to class_schema.
        - Define a default workflow to be overwritten if necessary, as an
          Enumerate until now.
        - Define a default view to display a comment ("comment_view").
        - Add comments view which displays comments on edit_mode, so that you
          can filter by workflow state and change state on any comment(s).
    """

    comments = CommentsView(access='is_allowed_to_edit', edit_mode=True)


    def get_comments(self, state=None):
        """ Get any comment matching given state.
            state may be a string, a tuple or a list.
        """
        abspath = str(self.abspath)
        comments = get_context().search(base_classes='comment',
                                        parent_paths=abspath)
        comments = comments.get_resources(sort_by='mtime')
        if state is None:
            return list(comments)

        if type(state) not in (tuple, list):
            state = [state]

        return [ x for x in comments
                 if x.get_value('comment_state') in state ]


    def add_comment(self, description, language=None):
        if language is None:
            root = self.get_resource('/')
            language = root.get_default_language()

        comment = self.make_resource(None, Comment)
        comment.set_value('description', description, language=language)
        return comment
