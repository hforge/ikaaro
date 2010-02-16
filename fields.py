# -*- coding: UTF-8 -*-
# Copyright (C) 2009 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from datetime import datetime

# Import from itools
from itools.core import get_abspath, thingy_property, thingy_lazy_property
from itools.core import OrderedDict
from itools.datatypes import Date, DateTime, Enumerate, String, Unicode
from itools.gettext import MSG
from itools.stl import make_stl_template
from itools.fs import lfs
from itools.web import hidden_field, input_field, text_field, textarea_field
from itools.web import file_field

# Import from ikaaro
from datatypes import HTMLBody


class file_preview_field(file_field):

    image_size = 128

    @thingy_lazy_property
    def preview(self):
        resource = self.view.resource
        try:
            resource.thumb
        except AttributeError:
            return None

        size = self.image_size
        return '%s/;thumb?width=%s&height=%s' % (resource.path, size, size)



class image_size_field(input_field):

    # Default values
    width = 0
    height = 0


    def decode(self, raw_value):
        try:
            self.width = self.height = int(raw_value)
        except ValueError:
            width, height = raw_value.split('x')
            self.width, self.height = int(width), int(height)


    def is_empty(self):
        return False


    def is_valid(self):
        return True


    @thingy_lazy_property
    def encoded_value(self):
        if self.raw_value:
            return self.raw_value
        return '%sx%s' % (self.width, self.height)



###########################################################################
# Date & Time fields
###########################################################################

class DateField(input_field):

    datatype = Date

    input_template = make_stl_template("""
    <input type="text" name="${name}" value="${encoded_value}" id="${id}"
      class="dateField" size="${size}" />
    <input type="button" value="..." class="${css}" />
    <script language="javascript">
      jQuery( "input.dateField" ).dynDateTime({
        ifFormat: "${format}",
        showsTime: ${show_time_js},
        timeFormat: "24",
        button: ".next()" });
    </script>""")

    css = None
    description = MSG(u"Format: 'yyyy-mm-dd'")
    format = '%Y-%m-%d'
    show_time = False
    size = None


    def show_time_js(self):
        # True -> true for Javascript
        return 'true' if self.show_time else 'false'


    def encoded_value(self):
        value = self.value
        if value is None:
            return ''

        # ['2007-08-01\r\n2007-08-02']
        if self.datatype.multiple and isinstance(value, list):
            return value[0]

        return value



class DateTimeField(input_field):

    datatype = DateTime

    input_template = make_stl_template("""
    <input type="text" name="${name}" value="${value_date}" id="${id}"
      class="dateField" size="${size}" />
    <input type="button" value="..." class="${css}" />
    <input type="text" name="${name}_time" value="${value_time}" size="6" />
    <script language="javascript">
      jQuery( "input.dateField" ).dynDateTime({
        ifFormat: "${format}",
        showsTime: ${show_time_js},
        timeFormat: "24",
        button: ".next()" });
    </script>
    """)


    css = None
    format = '%Y-%m-%d'
    size = None
    show_time = False

    def show_time_js(self):
        # True -> true for Javascript
        return 'true' if self.show_time else 'false'


    def value_date(self):
        return self.value.date()


    def value_time(self):
        return self.value.strftime('%H:%M')


    @thingy_lazy_property
    def raw_value(self):
        date = self.getter(self.name)
        if date is None:
            return None

        time = self.getter('%s_time' % self.name)
        return '%sT%s' % (date, time)



###########################################################################
# Advanced fields
###########################################################################

class RTEField(input_field):

    datatype = HTMLBody

    input_template = 'tiny_mce/rte.xml'
    rte_css = ['/ui/aruni/style.css', '/ui/tiny_mce/content.css']
    scripts = [
        '/ui/tiny_mce/tiny_mce_src.js',
        '/ui/tiny_mce/javascript.js']

    # Configuration
    # See http://wiki.moxiecode.com/index.php/TinyMCE:Configuration
    width = None
    height = '340px'
    # toolbar
    toolbar1 = (
        'newdocument,code,|,bold,italic,underline,strikethrough,|,justifyleft,'
        'justifycenter,justifyright, justifyfull,|,bullist,numlist,|, outdent,'
        'indent,|,undo,redo,|,link,unlink,image,media')
    toolbar2 = (
        'tablecontrols,|,removeformat,forecolor,backcolor,|,formatselect')
    toolbar3 = None
    resizing = True
    plugins = 'safari,table,media,advimage,advlink'
    # Extending the existing rule set.
    extended_valid_elements = None
    # css
    advanced_styles = None
    table_styles = None


    def language(self):
        path = get_abspath('ui/tiny_mce/langs')
        tiny_mce_languages = [ x[:-3] for x in lfs.get_names(path) ]
        accept = self.view.context.accept_language
        return accept.select_language(tiny_mce_languages)


    def css(self):
        return ','.join(self.rte_css)


    def resizing_js(self):
        return 'true' if self.resizing else 'false'



###########################################################################
# Ready to use fields
###########################################################################

class TimestampField(hidden_field):
    """This ready-to-use field is used to handle edit conflicts.
    """

    datatype = DateTime
    name = 'timestamp'

    @thingy_property
    def value(self):
        return datetime.now()


class NameField(input_field):
    value = ''
    name = 'name'
    title = MSG(u'Name')



def value(self):
    view = self.view
    return view.resource.get_value(self.name, language=view.content_language)


class description_field(textarea_field):
    name = 'description'
    title = MSG(u'Description')
    value = thingy_lazy_property(value)


class subject_field(text_field):
    name = 'subject'
    title = MSG(u'Keywords (Separated by comma)')
    value = thingy_lazy_property(value)


class title_field(text_field):
    name = 'title'
    title = MSG(u'Title')
    value = thingy_lazy_property(value)

