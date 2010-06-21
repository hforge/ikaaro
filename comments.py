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

# Import from itools
from itools.html import xhtml_uri
from itools.i18n import format_datetime
from itools.web import STLView
from itools.xml import START_ELEMENT, END_ELEMENT, TEXT


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

    def get_namespace(self, resource, context):
        root = context.root


        comments = resource.metadata.get_property('comment')
        if comments is None:
            comments = []
        else:
            comments = [
                {'number': i,
                 'user': root.get_user_title(x.parameters['author']),
                 'datetime': format_datetime(x.parameters['date']),
                 'comment': indent(x.value)}
                for i, x in enumerate(comments) ]
            comments.reverse()

        return {'comments': comments}
