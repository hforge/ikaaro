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
from itools.datatypes import is_datatype, DataType
from itools.datatypes import Unicode, Date, Enumerate, Boolean
from itools.gettext import MSG
from itools.html import sanitize_stream, stream_to_str_as_html
from itools.stl import stl
from itools.web import STLForm, get_context
from itools.xml import XMLParser, DocType


stl_namespaces = {
    None: 'http://www.w3.org/1999/xhtml',
    'stl': 'http://xml.itools.org/namespaces/stl'}
xhtml_namespaces = {None: 'http://www.w3.org/1999/xhtml'}
xhtml_doctype = DocType(
    '-//W3C//DTD XHTML 1.0 Strict//EN',
    'http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd')



###########################################################################
# DataTypes
###########################################################################
class HTMLBody(DataType):
    """TinyMCE specifics: read as XHTML, rendered as HTML.
    """
    sanitize_html = True


    @classmethod
    def decode(cls, data):
        events = XMLParser(data, namespaces=xhtml_namespaces,
                           doctype=xhtml_doctype)
        if cls.sanitize_html is True:
            events = sanitize_stream(events)
        return list(events)

    @staticmethod
    def encode(value):
        return stream_to_str_as_html(value)



###########################################################################
# Widgets
###########################################################################
def get_default_widget(datatype):
    if is_datatype(datatype, Unicode):
        if getattr(datatype, 'multiple', False) is True:
            return MultilineWidget
        return TextWidget
    elif is_datatype(datatype, Boolean):
        return BooleanCheckBox
    elif is_datatype(datatype, Date):
        return DateWidget
    elif is_datatype(datatype, Enumerate):
        return Select

    return TextWidget



class Widget(object):

    size = None

    template = list(XMLParser(
        """<input type="text" name="${name}" value="${value}" size="${size}"
        />""",
        stl_namespaces))


    def __init__(self, name, template=None, template_multiple=None, **kw):
        self.name = name
        if template is not None:
            self.template = template
        if template_multiple is not None:
            self.template_multiple = template_multiple
        for key in kw:
            setattr(self, key, kw[key])


    def get_prefix(self):
        return None


    def get_template(self, datatype, value):
        return self.template


    def get_namespace(self, datatype, value):
        return {
            'name': self.name,
            'value': value,
            'size': self.size}


    def to_html(self, datatype, value):
        template = self.get_template(datatype, value)
        namespace = self.get_namespace(datatype, value)
        prefix = self.get_prefix()
        return stl(events=template, namespace=namespace, prefix=prefix)



class TextWidget(Widget):

    size = 40



class HiddenWidget(Widget):

    template = list(XMLParser(
        """<input type="hidden" name="${name}" value="${value}" />""",
        stl_namespaces))


    def get_namespace(self, datatype, value):
        return {'name': self.name,
                'value': value}



class ReadOnlyWidget(Widget):

    template = list(XMLParser(
        """<input type="hidden" name="${name}" value="${value}" />
           ${displayed}""", stl_namespaces))


    def get_namespace(self, datatype, value):
        return {
            'name': self.name,
            'value': value,
            'displayed': getattr(self, 'displayed', value)}



class MultilineWidget(Widget):

    rows = 5
    cols = 60

    template = list(XMLParser(
        """<textarea rows="${rows}" cols="${cols}" name="${name}"
        >${value}</textarea>""",
        stl_namespaces))


    def get_namespace(self, datatype, value):
        return {
            'name': self.name,
            'value': value,
            'rows': self.rows,
            'cols': self.cols}



class CheckBoxWidget(Widget):

    template = list(XMLParser("""
        <input type="checkbox" name="${name}" value="${value}"
          checked="${is_selected}" />
        """, stl_namespaces))


    def get_namespace(self, datatype, value):
        return {
            'name': self.name,
            'value': value,
            'is_selected': getattr(self, 'is_selected', False)}



class BooleanCheckBox(Widget):

    template = list(XMLParser("""
        <input type="checkbox" name="${name}" value="1"
          checked="${is_selected}" />
        """, stl_namespaces))


    def get_namespace(self, datatype, value):
        return {
            'name': self.name,
            'is_selected': value in [True, 1, '1']}



class BooleanRadio(Widget):

    template = list(XMLParser("""
        <label for="${name}_yes">${labels/yes}</label>
        <input id="${name}_yes" name="${name}" type="radio" value="1"
          checked="checked" stl:if="is_yes"/>
        <input id="${name}_yes" name="${name}" type="radio" value="1"
          stl:if="not is_yes"/>

        <label for="${name}_no">${labels/no}</label>
        <input id="${name}_no" name="${name}" type="radio" value="0"
          checked="checked" stl:if="not is_yes"/>
        <input id="${name}_no" name="${name}" type="radio" value="0"
          stl:if="is_yes"/>
        """, stl_namespaces))


    def get_namespace(self, datatype, value):
        labels = getattr(self, 'labels', {'yes': 'Yes', 'no': 'No'})
        return {
            'name': self.name,
            'is_yes': value in [True, 1, '1'],
            'labels': labels}



class Select(Widget):

    template = list(XMLParser("""
        <select name="${name}" multiple="${multiple}">
          <option value=""></option>
          <option stl:repeat="option options" value="${option/name}"
            selected="${option/selected}">${option/value}</option>
        </select>
        """, stl_namespaces))


    def get_namespace(self, datatype, value):
        return {
            'name': self.name,
            'multiple': getattr(datatype, 'multiple', False),
            'options': datatype.get_namespace(value)}



class SelectRadio(Widget):

    template = list(XMLParser("""
        <input type="radio" name="${name}" value="" checked="checked"
          stl:if="none_selected"/>
        <input type="radio" name="${name}" value=""
          stl:if="not none_selected"/>
        <br/>
        <stl:block stl:repeat="option options">
          <input type="radio" id="${name}_${option/name}" name="${name}"
            value="${option/name}" checked="checked"
            stl:if="option/selected"/>
          <input type="radio" id="${name}_${option/name}" name="${name}"
            value="${option/name}" stl:if="not option/selected"/>
          <label for="${name}_${option/name}">${option/value}</label><br/>
        </stl:block>
        """, stl_namespaces))

    template_multiple = list(XMLParser("""
        <stl:block stl:repeat="option options">
          <input type="checkbox" name="${name}" id="${name}_${option/name}"
            value="${option/name}" checked="${option/selected}" />
          <label for="${name}_${option/name}">${option/value}</label><br/>
        </stl:block>
        """, stl_namespaces))


    def get_template(self, datatype, value):
        if getattr(datatype, 'multiple', False) is True:
            return self.template_multiple
        return self.template


    def get_namespace(self, datatype, value):
        none_selected = True
        options = datatype.get_namespace(value)
        for option in options:
            if option is True:
                none_selected = False
                break
        return {
            'name': self.name,
            'none_selected': none_selected,
            'options': options}


class DateWidget(Widget):

    template = list(XMLParser("""
        <input type="text" name="${name}" value="${value}" id="${name}" />
        <input id="trigger_date_${name}" type="button" value="..."
          name="trigger_date_${name}"/>
        <script language="javascript">
          Calendar.setup({inputField: "${name}", ifFormat: "${format}",
                          button: "trigger_date_${name}"});
        </script>
        """, stl_namespaces))

    template_multiple = list(XMLParser("""
        <table class="table_calendar">
          <tr>
            <td>
              <textarea rows="5" cols="25" name="${name}" id="${name}"
                >${value}</textarea>
              <input type="button" value="update" id="btn_blur_${name}"
                onclick="tableFlatOuputOnBlur(elt_${name}, cal_${name});" />
            </td>
            <td>
              <div id="calendar-flat-${name}" style="float: left;"> </div>
              <script type="text/javascript">
                var MA_${name} = [];
                <stl:block stl:repeat="date dates">
                MA_${name}.push(str_to_date('${date}'));
                </stl:block>
                var cal_${name} = Calendar.setup({
                    displayArea  : '${name}',
                    flat         : 'calendar-flat-${name}',
                    flatCallback : tableFlatCallback,
                    multiple     : MA_${name},
                    ifFormat     : '${format}'});
                var elt_${name} = document.getElementById('${name}');
                if (!browser.isIE) {
                    $("#btn_blur_${name}").style.display = 'none';
                    elt_${name}.setAttribute('onblur',
                        'tableFlatOuputOnBlur(elt_${name}, cal_${name})');
                }
              </script>
            </td>
          </tr>
        </table>
        """, stl_namespaces))


    def get_template(self, datatype, value):
        if getattr(datatype, 'multiple', False) is True:
            return self.template_multiple
        return self.template


    def get_namespace(self, datatype, value):
        if value is None:
            value = ''
        format = getattr(self, 'format', '%Y-%m-%d')

        if getattr(datatype, 'multiple', False) is True:
            if isinstance(value, list): # ['2007-08-01\r\n2007-08-02']
                value = value[0]
            return {
                'name': self.name, 'format': format, 'value': value,
                'dates': value.splitlines()}

        return {'name': self.name, 'format': format, 'value': value}



class RTEWidget(Widget):

    template = list(XMLParser("""${rte}""", stl_namespaces))

    rte_template = '/ui/tiny_mce/rte.xml'
    rte_css = ['/ui/aruni/aruni.css', '/ui/tiny_mce/content.css']
    rte_scripts = [
        '/ui/tiny_mce/tiny_mce_src.js',
        '/ui/tiny_mce/javascript.js']


    def get_rte_css(self):
        return self.rte_css


    def get_prefix(self):
        context = get_context()
        here = context.resource.get_abspath()
        prefix = here.get_pathto(self.rte_template)
        return prefix


    def get_template(self, datatype, value):
        context = get_context()
        handler = context.root.get_resource(self.rte_template)
        return handler.events


    def get_namespace(self, datatype, value):
        context = get_context()
        css_names = self.get_rte_css()
        return {'form_name': self.name,
                'source': value,
                'scripts': self.rte_scripts,
                'css': ','.join(css_names)}


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
    required_msg = None
    template = '/ui/auto_form.xml'


    def get_widgets(self, resource, context):
        return self.widgets


    def get_namespace(self, resource, context):
        here = context.resource
        # Local Variables
        fields = self.get_schema(resource, context)
        widgets = self.get_widgets(resource, context)

        # Set and translate the required_msg
        required_msg = self.required_msg
        if required_msg is None:
            required_msg = MSG(
                u'The <span class="field_is_required">emphasized</span> fields'
                u' are required.')
        required_msg = required_msg.gettext()
        required_msg = required_msg.encode('utf-8')
        required_msg = XMLParser(required_msg)

        # Build widgets namespace
        has_required_widget = False
        widgets_namespace = self.build_namespace(resource, context)
        ns_widgets = []
        for widget in widgets:
            datatype = fields[widget.name]
            is_mandatory = getattr(datatype, 'mandatory', False)
            if is_mandatory:
                has_required_widget = True
            widget_namespace = widgets_namespace[widget.name]
            value = widget_namespace['value']
            widget_namespace['title'] = getattr(widget, 'title', None)
            widget_namespace['mandatory'] = is_mandatory
            widget_namespace['multiple'] = getattr(datatype, 'multiple', False)
            widget_namespace['is_date'] = is_datatype(datatype, Date)
            widget_namespace['widget'] = widget.to_html(datatype, value)
            ns_widgets.append(widget_namespace)

        # Build namespace
        return {
            'title': self.get_title(context),
            'required_msg': required_msg,
            'first_widget': widgets[0].name,
            'action': context.uri,
            'submit_value': self.submit_value,
            'submit_class': self.submit_class,
            'widgets': ns_widgets,
            'has_required_widget': has_required_widget,
            }
