# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007-2008 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2008 Sylvain Taverne <sylvain@itaapy.com>
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
from itools.core import get_abspath, thingy_lazy_property
from itools.datatypes import DataType, Date, Enumerate, Boolean
from itools.fs import lfs
from itools.gettext import MSG
from itools.html import stream_to_str_as_xhtml, stream_to_str_as_html
from itools.html import xhtml_doctype, sanitize_stream
from itools.stl import stl
from itools.web import STLForm, get_context
from itools.xml import XMLParser

# Import from ikaaro
from utils import CMSTemplate



xhtml_namespaces = {None: 'http://www.w3.org/1999/xhtml'}



###########################################################################
# DataTypes
###########################################################################
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



###########################################################################
# Widgets
###########################################################################

stl_namespaces = {
    None: 'http://www.w3.org/1999/xhtml',
    'stl': 'http://www.hforge.org/xml-namespaces/stl'}
def make_stl_template(data):
    return list(XMLParser(data, stl_namespaces))



def get_default_widget(datatype):
    if issubclass(datatype, Boolean):
        return RadioWidget
    elif issubclass(datatype, Date):
        return DateWidget
    elif issubclass(datatype, Enumerate):
        return SelectWidget

    return TextWidget



class Widget(CMSTemplate):

    maxlength = None
    size = None
    suffix = None
    tip = None
    type = 'text'

    template = make_stl_template("""
    <input type="${type}" id="${id}" name="${name}" value="${value}"
      maxlength="${maxlength}" size="${size}" />""")


    def __init__(self, name=None, **kw):
        if name:
            self.name = name
        self.id = self.name.replace('_', '-')
        for key in kw:
            setattr(self, key, kw[key])



class TextWidget(Widget):

    size = 40



class HiddenWidget(Widget):

    type = 'hidden'



class FileWidget(Widget):

    type = 'file'



class PasswordWidget(Widget):

    type = 'password'



class ReadOnlyWidget(Widget):

    template = make_stl_template("""
    <input type="hidden" id="${id}" name="${name}" value="${value_}" />
    ${displayed_}""")

    displayed = None


    @thingy_lazy_property
    def value_(self):
        value = self.value
        if issubclass(self.datatype, Enumerate) and isinstance(value, list):
            for option in value:
                if option['selected']:
                    return option['name']
            return self.datatype.default
        return value


    def displayed_(self):
        if self.displayed is not None:
            return self.displayed

        value = self.value_
        if issubclass(self.datatype, Enumerate):
            return self.datatype.get_value(value)

        return value



class MultilineWidget(Widget):

    template = make_stl_template("""
    <textarea rows="${rows}" cols="${cols}" id="${id}" name="${name}"
    >${value}</textarea>""")

    rows = 5
    cols = 60



class RadioWidget(Widget):

    template = make_stl_template("""
    <stl:block stl:repeat="option options">
      <input type="radio" id="${id}-${option/name}" name="${name}"
        value="${option/name}" checked="${option/selected}" />
      <label for="${id}-${option/name}">${option/value}</label>
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
                    {'name': '', 'value': '',  'selected': False})

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
            yes_selected = value in [True, 1, '1']
            return [
                {'name': '1', 'value': labels['yes'], 'selected': yes_selected},
                {'name': '0', 'value': labels['no'],
                 'selected': not yes_selected}]

        # Case 3: Error
        err = 'datatype "%s" should be enumerate or boolean'
        raise ValueError, err % self.name



class CheckboxWidget(Widget):

    template = make_stl_template("""
    <stl:block stl:repeat="option options">
      <input type="checkbox" id="${id}-${option/name}" name="${name}"
        value="${option/name}" checked="${option/selected}" />
      <label for="${id}-${option/name}">${option/value}</label>
      <br stl:if="not oneline" />
    </stl:block>""")

    oneline = False


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
                return datatype.get_namespace(value)
            return value

        # Case 2: Boolean
        if issubclass(datatype, Boolean):
            return [{'name': '1', 'value': '',
                     'selected': value in [True, 1, '1']}]

        # Case 3: Error
        raise ValueError, 'expected boolean or enumerate datatype'



class SelectWidget(Widget):

    template = make_stl_template("""
    <select id="${id}" name="${name}" multiple="${multiple}" size="${size}"
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



class DateWidget(Widget):

    tip = MSG(u"Format: 'yyyy-mm-dd'")

    template = make_stl_template("""
    <input type="text" name="${name}" value="${value_}" id="${id}"
      class="dateField" size="${size}" />
    <button class="${css} button-selector">...</button>
    <script language="javascript">
      jQuery( "input.dateField" ).dynDateTime({
        ifFormat: "${format}",
        showsTime: ${show_time_js},
        timeFormat: "24",
        button: ".next()" });
    </script>""")


    css = None
    format = '%Y-%m-%d'
    size = None
    show_time = False

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


    def dates(self):
        return self.value_.splitlines()



class PathSelectorWidget(TextWidget):

    action = 'add_link'
    display_workflow = True

    template = make_stl_template("""
    <input type="text" id="selector-${id}" size="${size}" name="${name}"
      value="${value}" />
    <button id="selector-button-${id}" class="button-selector"
      name="selector_button_${name}"
      onclick="popup(';${action}?target_id=selector-${id}&amp;mode=input', 620, 300);">...</button>
    ${workflow_state}""")


    def workflow_state(self):
        from ikaaro.workflow import get_workflow_preview

        if self.display_workflow:
            value = self.value
            if type(value) is not str:
                value = self.datatype.encode(value)
            if value:
                context = get_context()
                resource = context.resource.get_resource(value, soft=True)
                if resource:
                    return get_workflow_preview(resource, context)

        return None



class ImageSelectorWidget(PathSelectorWidget):

    action = 'add_image'
    width = 128
    height = 128

    template = make_stl_template("""
    <input type="text" id="selector-${id}" size="${size}" name="${name}"
      value="${value}" />
    <button id="selector-button-${id}" class="button-selector"
      name="selector_button_${name}"
      onclick="popup(';${action}?target_id=selector-${id}&amp;mode=input', 620, 300);">...</button>
    ${workflow_state}
    <br/>
    <img src="${value}/;thumb?width=${width}&amp;height=${height}" stl:if="value"/>""")



class RTEWidget(Widget):

    template = '/ui/tiny_mce/rte.xml'
    rte_css = ['/ui/aruni/style.css', '/ui/tiny_mce/content.css']
    scripts = [
        '/ui/tiny_mce/tiny_mce_src.js',
        '/ui/tiny_mce/javascript.js']

    # Configuration
    # See http://wiki.moxiecode.com/index.php/TinyMCE:Configuration
    width = None
    height = '340px'
    # toolbar
    toolbar1 = ('newdocument,code,|,bold,italic,underline,strikethrough,|,'
                'justifyleft,justifycenter,justifyright, justifyfull,|,'
                'bullist,numlist,|, outdent, indent,|,undo,redo,|,link,'
                'unlink,image,media')
    toolbar2 = ('tablecontrols,|,removeformat,forecolor,backcolor,|,'
                'formatselect')
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
        languages = [ x[:-3] for x in lfs.get_names(path) ]
        return get_context().accept_language.select_language(languages)


    def css(self):
        return ','.join(self.rte_css)


    def resizing_js(self):
        return 'true' if self.resizing else 'false'


    def get_prefix(self):
        context = get_context()
        here = context.resource.get_abspath()
        prefix = here.get_pathto(self.template)
        return prefix


    def render(self):
        prefix = self.get_prefix()
        template = self.get_template()
        return stl(events=template, namespace=self, prefix=prefix)



###########################################################################
# Common widgets to reuse
###########################################################################
title_widget = TextWidget('title', title=MSG(u'Title'))
description_widget = MultilineWidget('description',
                                     title=MSG(u'Description'), rows=8)
subject_widget = TextWidget('subject',
                            title=MSG(u'Keywords (Separated by comma)'))
rte_widget = RTEWidget('data', title=MSG(u'Body'))
timestamp_widget = HiddenWidget('timestamp')
file_widget = FileWidget('file', title=MSG(u'Replace file'))


###########################################################################
# Generate Form
###########################################################################
class AutoForm(STLForm):
    """Fields is a dictionnary:

      {'firstname': Unicode(mandatory=True),
       'lastname': Unicode(mandatory=True)}

    Widgets is a list:

      [TextWidget('firstname', title=MSG(u'Firstname')),
       TextWidget('lastname', title=MSG(u'Lastname'))]
    """

    widgets = []
    template = '/ui/auto_form.xml'
    submit_value = MSG(u'Save')
    submit_class = 'button-ok'
    description = None


    def get_widgets(self, resource, context):
        return self.widgets


    def get_namespace(self, resource, context):
        widgets_namespace = STLForm.get_namespace(self, resource, context)

        # Local Variables
        fields = self.get_schema(resource, context)
        widgets = self.get_widgets(resource, context)

        # Build widgets namespace
        ns_widgets = []
        for widget in widgets:
            datatype = fields[widget.name]
            widget_namespace = widgets_namespace[widget.name]
            value = widget_namespace['value']
            widget_namespace['title'] = getattr(widget, 'title', None)
            is_mandatory = getattr(datatype, 'mandatory', False)
            widget_namespace['mandatory'] = is_mandatory
            widget_namespace['is_date'] = issubclass(datatype, Date)
            widget_namespace['suffix'] = widget.suffix
            widget_namespace['tip'] = widget.tip
            widget = widget(datatype=datatype, value=value)
            widget_namespace['widget'] = widget.render()
            ns_widgets.append(widget_namespace)

        for widget in widgets:
            if not issubclass(widget, ReadOnlyWidget):
                first_widget = widget.name
                break
        else:
            first_widget = None

        # Build namespace
        return {
            'title': self.get_title(context),
            'description': self.description,
            'first_widget': first_widget,
            'action': context.uri,
            'submit_value': self.submit_value,
            'submit_class': self.submit_class,
            'widgets': ns_widgets}

