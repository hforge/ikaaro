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
from marshal import dumps, loads
from urllib import quote, unquote
from zlib import compress, decompress

# Import from itools
from itools.core import freeze, guess_type
from itools.datatypes import DataType
from itools.html import xhtml_doctype, sanitize_stream
from itools.html import stream_to_str_as_xhtml, stream_to_str_as_html
from itools.xml import XMLParser


"""This module defines some datatypes used in ikaaro, whose inclusion in
itools is not yet clear.
"""


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



class HTMLBody(XHTMLBody):
    """TinyMCE specifics: read as XHTML, rendered as HTML.
    """

    @staticmethod
    def encode(value):
        if value is None:
            return ''
        return stream_to_str_as_html(value)



