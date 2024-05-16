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

from datetime import date

# Import from the Standard Library
from base64 import decodebytes, encodebytes
from datetime import timedelta
from urllib.parse import quote, unquote

# Import from itools
from itools.core import guess_type
from itools.datatypes import DataType, Date, Enumerate, String
from itools.fs import FileName
from itools.gettext import MSG
from itools.html import stream_to_str_as_xhtml, stream_to_str_as_html
from itools.html import xhtml_doctype, sanitize_stream, stream_is_empty
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



class Password_Datatype(DataType):

    @staticmethod
    def decode(data):
        data = unquote(data)
        data = data.encode()
        return decodebytes(data)


    @staticmethod
    def encode(value):
        if type(value) is str:
            value = value.encode("utf-8")
        return quote(encodebytes(value))


class ChoosePassword_Datatype(String):

    @staticmethod
    def is_valid(value):
        return len(value) >= 4



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
        if type(value) is str:
            return value.encode('utf-8')
        if not is_xml_stream(value):
            value = value.get_body().get_content_elements()
        return stream_to_str_as_html(value)



###########################################################################
# Enumerates
###########################################################################
days = {
    0: MSG('Monday'),
    1: MSG('Tuesday'),
    2: MSG('Wednesday'),
    3: MSG('Thursday'),
    4: MSG('Friday'),
    5: MSG('Saturday'),
    6: MSG('Sunday')}


class DaysOfWeek(Enumerate):

    options = [
        {'name': '1', 'value': MSG('Monday'), 'shortname': 'MO'},
        {'name': '2', 'value': MSG('Tuesday'), 'shortname': 'TU'},
        {'name': '3', 'value': MSG('Wednesday'), 'shortname': 'WE'},
        {'name': '4', 'value': MSG('Thursday'), 'shortname': 'TH'},
        {'name': '5', 'value': MSG('Friday'), 'shortname': 'FR'},
        {'name': '6', 'value': MSG('Saturday'), 'shortname': 'SA'},
        {'name': '7', 'value': MSG('Sunday'), 'shortname': 'SU'}]

    @classmethod
    def get_shortname(cls, name):
        for option in cls.options:
            if option['name'] == name:
                return option['shortname']


    @classmethod
    def get_name_by_shortname(cls, shortname):
        for option in cls.options:
            if option['shortname'] == shortname:
                return option['name']



class Boolean3(Enumerate):
    """ Boolean 3 states : Yes/No/Any useful on search form."""
    default = ''
    options = [
        #{'name': '', 'value': ''},
        {'name': '1', 'value': MSG('Yes')},
        {'name': '0', 'value': MSG('No')}]

    @staticmethod
    def decode(value):
        if value == '':
            return None
        return bool(int(value))


    @staticmethod
    def encode(value):
        if value is True:
            return '1'
        elif value is False:
            return '0'
        return None


    @staticmethod
    def is_valid(value):
        return value in (True, False, None)


    def get_namespace(cls, name):
        if name in (True, False, None):
            name = Boolean3.encode(name)
        return Enumerate(options=cls.get_options()).get_namespace(name)



class IntegerRange(Enumerate):
    count = 4

    @classmethod
    def get_options(cls):
        return [
            {'name': str(i), 'value': str(i)} for i in range(1, cls.count) ]



class Days(IntegerRange):
    count = 32



class Months(Enumerate):

    options = [
        {'name': '1', 'value': MSG('January')},
        {'name': '2', 'value': MSG('February')},
        {'name': '3', 'value': MSG('March')},
        {'name': '4', 'value': MSG('April')},
        {'name': '5', 'value': MSG('May')},
        {'name': '6', 'value': MSG('June')},
        {'name': '7', 'value': MSG('July')},
        {'name': '8', 'value': MSG('August')},
        {'name': '9', 'value': MSG('September')},
        {'name': '10', 'value': MSG('October')},
        {'name': '11', 'value': MSG('November')},
        {'name': '12', 'value': MSG('December')}]



class Years(Enumerate):

    start = 1900

    @classmethod
    def get_options(cls):
        return [{'name': str(d), 'value': str(d)}
                 for d in range(cls.start, date.today().year)]
