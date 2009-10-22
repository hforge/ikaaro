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

# Import from itools
from itools.core import thingy_lazy_property
from itools.datatypes import Date, DateTime, Email, String, Unicode
from itools.gettext import MSG
from itools.web import ViewField
from itools.xml import XMLParser

# Import from ikaaro
from datatypes import FileDataType, HTMLBody
from utils import CMSTemplate



###########################################################################
# Utilities
###########################################################################

stl_namespaces = {
    None: 'http://www.w3.org/1999/xhtml',
    'stl': 'http://www.hforge.org/xml-namespaces/stl'}

def make_stl_template(data):
    return list(XMLParser(data, stl_namespaces))




###########################################################################
# Widgets
###########################################################################

class Widget(CMSTemplate):

    def __init__(self, name=None, **kw):
        if name:
            self.name = name
        for key in kw:
            setattr(self, key, kw[key])



class DateWidget(Widget):

    template = make_stl_template("""
    <input type="text" name="${name}" value="${value_}" id="${id}"
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


    @thingy_lazy_property
    def value_(self):
        value = self.value
        if value is None:
            return ''

        # ['2007-08-01\r\n2007-08-02']
        if self.datatype.multiple and isinstance(value, list):
            return value[0]

        return value



class DateTimeWidget(Widget):

    template = make_stl_template("""
    <input type="text" name="${name}" value="${value_date}" id="${name}"
      size="${size}"/>
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



class Input(Widget):

    template = make_stl_template("""
    <input type="${type}" name="${name}" value="${value}" size="${size}" />""")

    size = None
    type = None



FileInput = Input(type='file')
HiddenInput = Input(type='hidden')
PasswordInput = Input(type='password')
TextInput = Input(type='text', size=40)



class RadioInput(Widget):

    template = make_stl_template("""
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
            # Check whether the value is already a list of options
            # FIXME This is done to avoid a bug when using a select widget in
            # an auto-form, where the 'datatype.get_namespace' method is
            # called twice (there may be a better way of handling this).
            if type(value) is not list:
                options = datatype.get_namespace(value)
            else:
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



class RTEWidget(Widget):

    template = 'tiny_mce/rte.xml'
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
        accept = get_context().accept_language
        return accept.select_language(tiny_mce_languages)


    def css(self):
        return ','.join(self.rte_css)


    def resizing_js(self):
        return 'true' if self.resizing else 'false'



class Select(Widget):

    template = make_stl_template("""
    <select name="${name}" multiple="${multiple}" size="${size}"
        class="${css}">
      <option value="" stl:if="has_empty_option"></option>
      <option stl:repeat="option options" value="${option/name}"
        selected="${option/selected}">${option/value}</option>
    </select>""")


    css = None
    has_empty_option = True
    size = None


    def multiple(self):
        return self.datatype.multiple


    def options(self):
        value = self.value
        # Check whether the value is already a list of options
        # FIXME This is done to avoid a bug when using a select widget in an
        # auto-form, where the 'datatype.get_namespace' method is called
        # twice (there may be a better way of handling this).
        if type(value) is not list:
            return self.datatype.get_namespace(value)
        return value



class Textarea(Widget):

    template = make_stl_template("""
    <textarea rows="${rows}" cols="${cols}" name="${name}" >${value}</textarea>
    """)

    rows = 5
    cols = 60



###########################################################################
# Fields (basic)
###########################################################################
class FormField(ViewField, CMSTemplate):

    template = make_stl_template("""
    <label for="${name}">${title}</label>
    <span stl:if="required" class="field-is-required"
      title="This field is required">*</span>
    <span stl:if="description" title="${description}">(?)</span>
    <br/>
    <span stl:if="error" class="field-error">${error}<br/></span>
    ${widget_}""")


    description = None
    error = None
    title = None
    widget = None


    def widget_(self):
        return self.widget(name=self.name, datatype=self.datatype,
                           value=self.value)



class DateField(FormField):
    datatype = Date
    widget = DateWidget


class DateTimeField(FormField):
    datatype = DateTime
    widget = DateTimeWidget


class FileField(FormField):
    datatype = FileDataType
    widget = FileInput


class EmailField(FormField):
    datatype = Email
    widget = TextInput


class PasswordField(FormField):
    widget = PasswordInput


class RadioField(FormField):
    widget = RadioInput


class RTEField(FormField):
    datatype = HTMLBody
    widget = RTEWidget


class SelectField(FormField):
    widget = Select


class TextField(FormField):
    datatype = Unicode
    widget = TextInput



###########################################################################
# Fields (ready-to-use)
###########################################################################
class TimestampField(FormField):
    """This ready-to-use field is used to handle edit conflicts.
    """

    template = make_stl_template("""${widget}""")

    name = 'timestamp'
    datatype = DateTime
    readonly = True
    widget = HiddenInput



class DescriptionField(TextField):

    name = 'description'
    title = MSG(u'Description')
    widget = Textarea(rows=8)



# file (replace)
ReplaceFileField = FileField('file', title=MSG(u'Replace file'))
# name
NameField = TextField('name', datatype=String(default=''), title=MSG(u'Name'))
# subject
SubjectField = TextField(name='subject')
SubjectField.title = MSG(u'Keywords (Separated by comma)')
# title
TitleField = TextField('title', title=MSG(u'Title'))

