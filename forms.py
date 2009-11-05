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
from itertools import chain

# Import from itools
from itools.core import thingy_property
from itools.datatypes import Date, DateTime, Email, Enumerate, String, Unicode
from itools.gettext import MSG
from itools.stl import stl
from itools.web import ViewField
from itools.xml import XMLParser

# Import from ikaaro
from datatypes import FileDataType, HTMLBody



###########################################################################
# Utilities
###########################################################################

stl_namespaces = {
    None: 'http://www.w3.org/1999/xhtml',
    'stl': 'http://www.hforge.org/xml-namespaces/stl'}

def make_stl_template(data):
    return list(XMLParser(data, stl_namespaces))



###########################################################################
# Base class
###########################################################################

class FormField(ViewField):

    # First block: the field header
    header = make_stl_template("""
    <label for="${name}">${title}</label>
    <span stl:if="required" class="field-is-required"
      title="This field is required">*</span>
    <span stl:if="description" title="${description}">(?)</span>
    <br/>
    <span stl:if="error" class="field-error">${error}<br/></span>
    """)

    description = None
    error = None
    title = None

    # Second block: the form widget (by default an input element)
    widget = make_stl_template("""
    <input type="${type}" name="${name}" value="${encoded_value}"
      size="${size}" />""")

    size = None
    type = None


    def encoded_value(self):
        if self.value is None:
            return None
        return self.datatype.encode(self.value)


    def render(self):
        args = []

        # (1) The header
        if self.header:
            args.append(self.header)

        # (2) The widget
        widget = self.widget
        if widget is None:
            pass
        elif type(widget) is list:
            args.append(widget)
        elif type(widget) is str:
            widget = self.view.context.get_template(widget)
            widget = widget.events
            args.append(widget)
        else:
            raise TypeError, 'unexepected value of type "%s"' % type(widget)

        # Render
        events = chain(*args)
        events = list(events)
        return stl(events=events, namespace=self)



###########################################################################
# Simple fields
###########################################################################

class EmailField(FormField):
    datatype = Email
    size = 40



class FileField(FormField):
    datatype = FileDataType
    type = 'file'



class HiddenField(FormField):
    header = None
    readonly = True
    type = 'hidden'


class PasswordField(FormField):
    type = 'password'



class TextField(FormField):
    datatype = Unicode
    size = 40



class TextareaField(FormField):
    datatype = Unicode

    widget = make_stl_template("""
    <textarea rows="${rows}" cols="${cols}" name="${name}" >${value}</textarea>
    """)

    rows = 5
    cols = 60



###########################################################################
# Selection fields (radio buttons, checkboxes, selects)
###########################################################################

class RadioField(FormField):

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



class SelectField(FormField):

    widget = make_stl_template("""
    <select name="${name}" multiple="${multiple}" size="${size}"
        class="${css}">
      <option value="" stl:if="has_empty_option"></option>
      <option stl:repeat="option options" value="${option/value}"
        selected="${option/selected}">${option/title}</option>
    </select>""")


    css = None
    datatype = Enumerate
    has_empty_option = True
    size = None


    def options(self):
        value = self.value
        if self.multiple:
            f = lambda x, value=value: (x in value)
        else:
            f = lambda x, value=value: (x == value)

        return [
            {'value': x, 'title': self.get_value_title(x), 'selected': f(x) }
            for x in self.values ]


    @thingy_property
    def values(self):
        return self.datatype.values


    def get_value_title(self, value):
        return value


###########################################################################
# Date & Time fields
###########################################################################

class DateField(FormField):

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



class DateTimeField(FormField):

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

class RTEField(FormField):

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

class TimestampField(HiddenField):
    """This ready-to-use field is used to handle edit conflicts.
    """

    datatype = DateTime
    name = 'timestamp'

    def get_default(self):
        return datetime.now()


class DescriptionField(TextareaField):
    name = 'description'
    rows = 8
    title = MSG(u'Description')


class ReplaceFileField(FileField):
    name = 'file'
    title = MSG(u'Replace file')


class NameField(FormField):
    datatype = String(default='')
    name = 'name'
    title = MSG(u'Name')


class SubjectField(TextField):
    name = 'subject'
    title = MSG(u'Keywords (Separated by comma)')


class TitleField(TextField):
    name = 'title'
    title = MSG(u'Title')

