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
from itools.datatypes import String, DateTime
from itools.html import xhtml_uri
from itools.web import STLView
from itools.xml import START_ELEMENT, END_ELEMENT, TEXT

# Import from ikaaro
from fields import Text_Field


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



class CommentsView(STLView):

    template = '/ui/comments.xml'

    comment_columns = ['user', 'datetime', 'comment']

    def get_comment_columns(self, resource, context):
        return self.comment_columns


    def get_item_value(self, resource, context, item, column):
        if column == 'user':
            return context.root.get_user_title(item.get_parameter('author'))
        elif column == 'datetime':
            return context.format_datetime(item.get_parameter('date'))
        elif column == 'comment':
            return indent(item.value)
        raise ValueError, 'unexpected "%s" column' % column


    def get_namespace(self, resource, context):
        _comments = resource.metadata.get_property('comment') or []
        comments = []
        columns = self.get_comment_columns(resource, context)

        for i, comment in enumerate(_comments):
            ns = {'number': i}
            for key in columns:
                ns[key] = self.get_item_value(resource, context, comment, key)
            comments.append(ns)
        comments.reverse()

        return {'comments': comments}



class CommentsAware(object):

    comment = Text_Field(multilingual=False, multiple=True,
                         parameters_schema={'date': DateTime,
                                            'author': String,
                                            'state': String})
