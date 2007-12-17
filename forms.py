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
from itools.stl import stl
from itools.xml import XMLParser



namespaces = {
    None: 'http://www.w3.org/1999/xhtml',
    'stl': 'http://xml.itools.org/namespaces/stl'}


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

    @staticmethod
    def to_html(datatype, name, value):
        namespace = {}
        namespace['name'] = name
        namespace['value'] = value

        return stl(events=Widget.template, namespace=namespace)



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

    @staticmethod
    def to_html(datatype, name, value, displayed=None):
        namespace = {}
        namespace['name'] = name
        namespace['value'] = value
        namespace['displayed'] = value
        if displayed is not None:
            namespace['displayed'] = displayed
        return stl(events=ReadOnlyWidget.template, namespace=namespace)



class MultilineWidget(Widget):

    template = list(XMLParser(
        """<textarea rows="5" cols="25" name="${name}">${value}</textarea>""",
        namespaces))

    @staticmethod
    def to_html(datatype, name, value):
        namespace = {}
        namespace['name'] = name
        namespace['value'] = value

        return stl(events=MultilineWidget.template, namespace=namespace)



class CheckBoxWidget(Widget):

    template = list(XMLParser("""
        <input type="checkbox" name="${name}" value="${value}"
          checked="${is_selected}" />
        """, namespaces))

    @staticmethod
    def to_html(datatype, name, value, is_selected):
        namespace = {}
        namespace['name'] = name
        namespace['value'] = value
        namespace['is_selected'] = is_selected

        return stl(events=CheckBoxWidget.template, namespace=namespace)



class BooleanCheckBox(Widget):

    template = list(XMLParser("""
        <input type="checkbox" name="${name}" value="1"
          checked="${is_selected}" />
        """, namespaces))

    @staticmethod
    def to_html(datatype, name, value):
        namespace = {}
        namespace['name'] = name
        namespace['is_selected'] = value in [True, 1, '1']

        return stl(events=BooleanCheckBox.template, namespace=namespace)



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

    @staticmethod
    def to_html(datatype, name, value, labels={'yes': 'Yes', 'no': 'No'}):
        namespace = {}
        namespace['name'] = name
        namespace['is_yes'] = value in [True, 1, '1']
        namespace['labels'] = labels

        return stl(events=BooleanRadio.template, namespace=namespace)



class Select(Widget):

    template = list(XMLParser("""
        <select name="${name}" style="width: 200px" multiple="${multiple}">
          <option value=""></option>
          <option stl:repeat="option options" value="${option/name}"
            selected="${option/selected}">${option/value}</option>
        </select>
        """, namespaces))

    @staticmethod
    def to_html(datatype, name, value):
        namespace = {}
        namespace['name'] = name
        namespace['multiple'] = getattr(datatype, 'multiple', False)
        namespace['options'] = datatype.get_namespace(value)

        return stl(events=Select.template, namespace=namespace)


class SelectRadio(Widget):

    template_simple = list(XMLParser("""
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

    @staticmethod
    def to_html(datatype, name, value):
        namespace = {}
        namespace['name'] = name
        none_selected = True
        options = datatype.get_namespace(value)
        for option in options:
            if option is True:
                none_selected = False
                break
        namespace['none_selected'] = none_selected
        namespace['options'] = options
        if getattr(datatype, 'multiple', False) is True:
            return stl(events=SelectRadio.template_multiple,
                       namespace=namespace)
        else:
            return stl(events=SelectRadio.template_simple, namespace=namespace)


class DateWidget(Widget):

    template_simple = list(XMLParser("""
        <input type="text" name="${name}" value="${value}" id="${name}" />
        <input id="trigger_date" type="button" value="..."
          name="trigger_date"/>
        <script language="javascript">
          Calendar.setup({inputField: "${name}", ifFormat: "%Y-%m-%d",
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
                    ifFormat     : '%Y-%m-%d'});
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

    @staticmethod
    def to_html(datatype, name, value):
        if not value:
            value = ''
        namespace = {}
        namespace['name'] = name
        if getattr(datatype, 'multiple', False) is False:
            namespace['value'] = value
            return stl(events=DateWidget.template_simple, namespace=namespace)
        if isinstance(value, list): # ['2007-08-01\r\n2007-08-02']
            value = value[0]
        namespace['value'] = value
        namespace['dates'] = value.splitlines()
        return stl(events=DateWidget.template_multiple, namespace=namespace)
