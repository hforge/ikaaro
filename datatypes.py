# -*- coding: UTF-8 -*-
# Copyright (C) 2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from base64 import decodestring, encodestring
from datetime import timedelta
from marshal import dumps, loads
from urllib import quote, unquote
from zlib import compress, decompress

# Import from itools
from itools.core import freeze, guess_type
from itools.datatypes import DataType, Date, Enumerate, String
from itools.fs import FileName
from itools.gettext import MSG
from itools.html import stream_to_str_as_xhtml, stream_to_str_as_html
from itools.html import xhtml_doctype, sanitize_stream, stream_is_empty
from itools.web import get_context
from itools.xml import XMLParser, is_xml_stream


"""This module defines some datatypes used in ikaaro, whose inclusion in
itools is not yet clear.
"""


encoding_map = {
    'gzip': 'application/x-gzip',
    'bzip2': 'application/x-bzip2'}
def guess_mimetype(filename, default):
    """Override itools function 'guess_type' to intercept the encoding.
    """
    name, extension, language = FileName.decode(filename)
    filename = FileName.encode((name, extension, None))

    mimetype, encoding = guess_type(filename)
    return encoding_map.get(encoding, mimetype or default)



class FileDataType(DataType):
    """FIXME This datatype is special in that it does not deserializes from
    a byte string, but from a tuple.  Some day we should find a correct
    solution.
    """
    @staticmethod
    def encode(value):
        """Cannot preload anything in a file input.
        """
        return None


    @staticmethod
    def decode(data):
        """Find out the resource class (the mimetype sent by the browser can be
        minimalistic).
        """
        filename, mimetype, body = data
        mimetype = guess_mimetype(filename, mimetype)
        return filename, mimetype, body



class Password(DataType):

    @staticmethod
    def decode(data):
        return decodestring(unquote(data))


    @staticmethod
    def encode(value):
        return quote(encodestring(value))



class CopyCookie(DataType):

    default = None, freeze([])

    @staticmethod
    def encode(value):
        return quote(compress(dumps(value), 9))


    @staticmethod
    def decode(str):
        return loads(decompress(unquote(str)))



class ExpireValue(DataType):
    @staticmethod
    def decode(value):
        return timedelta(minutes=int(value))


    @staticmethod
    def encode(value):
        return str(int(value.total_seconds() / 60))


class BirthDate(Date):
    pass



class HexadecimalColor(String):

    @staticmethod
    def is_valid(value):
        return value.startswith('#') and len(value) == 7


###########################################################################
# HTML
###########################################################################
xhtml_namespaces = {None: 'http://www.w3.org/1999/xhtml'}



class XHTMLBody(DataType):
    """Read and write XHTML.
    """
    sanitize_html = True

    def decode(cls, data):
        events = XMLParser(data, namespaces=xhtml_namespaces,
                           doctype=xhtml_doctype)
        if cls.sanitize_html is True:
            events = sanitize_stream(events)
        return list(events)


    @staticmethod
    def encode(value):
        if value is None:
            return ''
        return stream_to_str_as_xhtml(value)


    @staticmethod
    def is_empty(value):
        return stream_is_empty(value)



class HTMLBody(XHTMLBody):
    """TinyMCE specifics: read as XHTML, rendered as HTML.
    """

    @staticmethod
    def encode(value):
        if value is None:
            return ''
        if type(value) is unicode:
            return value.encode('utf-8')
        if not is_xml_stream(value):
            value = value.get_body().get_content_elements()
        return stream_to_str_as_html(value)


###########################################################################
# Groups
###########################################################################

class UserGroups_Datatype(Enumerate):

    def get_options(self):
        # FIXME Return the resources in order
        context = get_context()
        groups = context.search(parent_paths='/config/groups')
        return [
            {'name': str(x.abspath), 'value': x.get_title() }
            for x in groups.get_resources() ]



class Groups_Datatype(UserGroups_Datatype):

    special_groups = [
        {'name': 'everybody', 'value': MSG(u'Everybody')},
        {'name': 'authenticated', 'value': MSG(u'Authenticated')}]


    def get_options(self):
        options = super(Groups_Datatype, self).get_options()
        return self.special_groups + options
