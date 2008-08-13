# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Nicolas Deram <nicolas@itaapy.com>
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
from itools.datatypes import is_datatype, Unicode, Date, Enumerate, Boolean
from itools.gettext import MSG
from itools.stl import stl
from itools.web import STLForm
from itools.xml import XMLParser



namespaces = {
    None: 'http://www.w3.org/1999/xhtml',
    'stl': 'http://xml.itools.org/namespaces/stl'}


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
    else:
        return TextWidget



class Widget(object):

    template = list(XMLParser(
        """<input type="text" name="${name}" value="${value}" />""",
        namespaces))


    def __init__(self, name, template=None, template_multiple=None, **kw):
        self.name = name
        if template is not None:
            self.template = template
        if template_multiple is not None:
            self.template_multiple = template_multiple
        for key in kw:
            setattr(self, key, kw[key])


    def to_html(self, datatype, value):
        namespace = {}
        namespace['name'] = self.name
        namespace['value'] = value

        return stl(events=self.template, namespace=namespace)



class TextWidget(Widget):

    pass



class ReadOnlyWidget(Widget):

    template = list(XMLParser(
        """
        <stl:block xmlns="http://www.w3.org/1999/xhtml"
                   xmlns:stl="http://xml.itools.org/namespaces/stl">
            <input type="hidden" name="${name}" value="${value}" />
            ${displayed}
        </stl:block>
        """))


    def to_html(self, datatype, value):
        namespace = {}
        namespace['name'] = self.name
        namespace['value'] = value
        namespace['displayed'] = value
        displayed = getattr(self, 'displayed', None)
        if displayed is not None:
            namespace['displayed'] = displayed
        return stl(events=self.template, namespace=namespace)



class MultilineWidget(Widget):

    template = list(XMLParser(
        """<textarea rows="5" cols="25" name="${name}">${value}</textarea>""",
        namespaces))


    def to_html(self, datatype, value):
        namespace = {}
        namespace['name'] = self.name
        namespace['value'] = value

        return stl(events=self.template, namespace=namespace)



class CheckBoxWidget(Widget):

    template = list(XMLParser("""
        <input type="checkbox" name="${name}" value="${value}"
          checked="${is_selected}" />
        """, namespaces))


    def to_html(self, datatype, value):
        namespace = {}
        namespace['name'] = self.name
        namespace['value'] = value
        namespace['is_selected'] = getattr(self, 'is_selected', False)

        return stl(events=self.template, namespace=namespace)



class BooleanCheckBox(Widget):

    template = list(XMLParser("""
        <input type="checkbox" name="${name}" value="1"
          checked="${is_selected}" />
        """, namespaces))


    def to_html(self, datatype, value):
        namespace = {}
        namespace['name'] = self.name
        namespace['is_selected'] = value in [True, 1, '1']

        return stl(events=self.template, namespace=namespace)



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
        """, namespaces))


    def to_html(self, datatype, value):
        namespace = {}
        namespace['name'] = self.name
        namespace['is_yes'] = value in [True, 1, '1']
        labels = getattr(self, 'labels', {'yes': 'Yes', 'no': 'No'})
        namespace['labels'] = labels

        return stl(events=self.template, namespace=namespace)



class Select(Widget):

    template = list(XMLParser("""
        <select name="${name}" multiple="${multiple}">
          <option value=""></option>
          <option stl:repeat="option options" value="${option/name}"
            selected="${option/selected}">${option/value}</option>
        </select>
        """, namespaces))


    def to_html(self, datatype, value):
        namespace = {}
        namespace['name'] = self.name
        namespace['multiple'] = getattr(datatype, 'multiple', False)
        namespace['options'] = datatype.get_namespace(value)

        return stl(events=self.template, namespace=namespace)


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
        """, namespaces))

    template_multiple = list(XMLParser("""
        <stl:block stl:repeat="option options">
          <input type="checkbox" name="${name}" id="${name}_${option/name}"
            value="${option/name}" checked="${option/selected}" />
          <label for="${name}_${option/name}">${option/value}</label><br/>
        </stl:block>
        """, namespaces))


    def to_html(self, datatype, value):
        namespace = {}
        namespace['name'] = self.name
        none_selected = True
        options = datatype.get_namespace(value)
        for option in options:
            if option is True:
                none_selected = False
                break
        namespace['none_selected'] = none_selected
        namespace['options'] = options
        if getattr(datatype, 'multiple', False) is True:
            return stl(events=self.template_multiple,
                       namespace=namespace)
        else:
            return stl(events=self.template, namespace=namespace)


class DateWidget(Widget):

    template = list(XMLParser("""
        <input type="text" name="${name}" value="${value}" id="${name}" />
        <input id="trigger_date" type="button" value="..."
          name="trigger_date"/>
        <script language="javascript">
          Calendar.setup({inputField: "${name}", ifFormat: "${format}",
                          button: "trigger_date"});
        </script>
        """, namespaces))

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
                    document.getElementById('btn_blur_${name}').style.display = 'none';
                    elt_${name}.setAttribute('onblur',
                        'tableFlatOuputOnBlur(elt_${name}, cal_${name})');
                }
              </script>
            </td>
          </tr>
        </table>
        """, namespaces))


    def to_html(self, datatype, value):
        if not value:
            value = ''
        namespace = {}
        namespace['name'] = self.name
        namespace['format'] = getattr(self, 'format', '%Y-%m-%d')
        if getattr(datatype, 'multiple', False) is False:
            namespace['value'] = value
            return stl(events=self.template, namespace=namespace)
        if isinstance(value, list): # ['2007-08-01\r\n2007-08-02']
            value = value[0]
        namespace['value'] = value
        namespace['dates'] = value.splitlines()
        return stl(events=self.template_multiple, namespace=namespace)



###########################################################################
# Generate Form
###########################################################################
class AutoForm(STLForm):
    """Fields is a dictionnary:

      {'firstname': Unicode(mandatory=True),
       'lastname': Unicode(mandatory=True)}

    Widgets is a list:

      [TextWidget('firstname', title=u'Firstname'),
       TextWidget('lastname', title=u'Lastname')]
    """

    widgets = []
    required_msg = None
    method = None
    template = '/ui/auto_form.xml'


    def get_widgets(self, resource, context):
        return self.widgets


    def get_namespace(self, resource, context):
        here = context.resource
        # Local Variables
        fields = self.get_schema(resource, context)
        widgets = self.get_widgets(resource, context)
        method = self.method

        # Set and translate the required_msg
        required_msg = self.required_msg
        if required_msg is None:
            required_msg = MSG(
                u'The <span class="field_required">emphasized</span> fields'
                u' are required.')
        required_msg = required_msg.gettext()
        required_msg = required_msg.encode('utf-8')
        required_msg = XMLParser(required_msg)

        # Build namespace
        namespace = {}
        namespace['title'] = self.get_form_title(context)
        namespace['required_msg'] = required_msg
        namespace['first_widget'] = widgets[0].name
        namespace['action'] = context.uri
        namespace['submit_value'] = self.submit_value
        namespace['submit_class'] = self.submit_class
        # Build widgets namespace
        has_required_widget = False
        widgets_namespace = context.build_form_namespace(fields, method=method)
        namespace['widgets'] = []
        for widget in widgets:
            datatype = fields[widget.name]
            is_mandatory = getattr(datatype, 'mandatory', False)
            if is_mandatory:
                has_required_widget = True
            widget_namespace = widgets_namespace[widget.name]
            value = widget_namespace['value']
            widget_namespace['title'] = getattr(widget, 'title', widget.name)
            widget_namespace['mandatory'] = is_mandatory
            widget_namespace['multiple'] = getattr(datatype, 'multiple', False)
            widget_namespace['is_date'] = is_datatype(datatype, Date)
            widget_namespace['widget'] = widget.to_html(datatype, value)
            namespace['widgets'].append(widget_namespace)
        namespace['has_required_widget'] = has_required_widget

        return namespace
