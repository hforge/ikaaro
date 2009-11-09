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
from itools.core import get_abspath, thingy_property
from itools.datatypes import Date, DateTime, Enumerate, String, Unicode
from itools.gettext import MSG
from itools import vfs
from itools.web import hidden_field, input_field, text_field, textarea_field
from itools.web import make_stl_template

# Import from ikaaro
from datatypes import HTMLBody



class RadioField(input_field):

    widget = make_stl_template("""
    <stl:block stl:repeat="option options">
      <input type="radio" id="${name}-${option/name}" name="${name}"
        value="${option/name}" checked="${option/selected}" />
      <label for="${name}-${option/name}">${option/value}</label>
      <br stl:if="not oneline" />
    </stl:block>""")

    oneline = False
    has_empty_option = True # Only makes sense for enumerates
                            # FIXME Do this other way


    def options(self):
        datatype = self.datatype
        value = self.value

        # Case 1: Enumerate
        if issubclass(datatype, Enumerate):
            options = value

            # Empty option
            if self.has_empty_option:
                options.insert(0,
                    {'name': '', 'value': '',  'is_selected': False})

            # Select first item if none selected
            for option in options:
                if option['selected'] is True:
                    return options

            if options:
                options[0]['selected'] = True
            return options

        # Case 2: Boolean
        if issubclass(datatype, Boolean):
            default_labels = {'yes': MSG(u'Yes'), 'no': MSG(u'No')}
            labels = getattr(self, 'labels', default_labels)
            return [
                {'name': '1', 'value': labels['yes'], 'is_selected': value},
                {'name': '0', 'value': labels['no'], 'is_selected': not value}]

        # Case 3: Error
        err = 'datatype "%s" should be enumerate or boolean'
        raise ValueError, err % self.name



###########################################################################
# Date & Time fields
###########################################################################

class DateField(input_field):

    datatype = Date

    widget = make_stl_template("""
    <input type="text" name="${name}" value="${encoded_value}" id="${id}"
      class="dateField" size="${size}" />
    <input type="button" value="..." class="${class}" />
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

    widget = make_stl_template("""
    <input type="text" name="${name}" value="${value_date}" id="${id}"
      class="dateField" size="${size}" />
    <input type="button" value="..." class="${class}" />
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


    def get_value(self, source):
        date = source.get(self.name)
        if date is None:
            return None

        time = source.get('%s_time' % self.name)
        return '%sT%s' % (date, time)



###########################################################################
# Advanced fields
###########################################################################

class RTEField(input_field):

    datatype = HTMLBody

    widget = 'tiny_mce/rte.xml'
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
        tiny_mce_languages = [ x[:-3] for x in vfs.get_names(path) ]
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
    def default(self):
        return datetime.now()


class DescriptionField(textarea_field):
    name = 'description'
    rows = 8
    title = MSG(u'Description')


class NameField(input_field):
    default = ''
    name = 'name'
    title = MSG(u'Name')


class SubjectField(text_field):
    name = 'subject'
    title = MSG(u'Keywords (Separated by comma)')


class TitleField(text_field):
    name = 'title'
    title = MSG(u'Title')

