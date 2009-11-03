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
from itools.datatypes import Date, Enumerate, Boolean
from itools.gettext import MSG
from itools.http import get_context
from itools import vfs
from itools.web import STLForm

# Import from ikaaro
from forms import DateField, FormField, RadioField, SelectField, TextField
from forms import make_stl_template
from ikaaro.workflow import get_workflow_preview



def get_default_field(datatype):
    if issubclass(datatype, Boolean):
        return RadioField
    elif issubclass(datatype, Date):
        return DateField
    elif issubclass(datatype, Enumerate):
        return SelectField

    return TextField



class ReadOnlyWidget(object):

    template = make_stl_template("""
    <input type="hidden" name="${name}" value="${value_}" />${displayed_}""")

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




class CheckboxWidget(object):

    template = make_stl_template("""
    <stl:block stl:repeat="option options">
      <input type="checkbox" id="${name}-${option/name}" name="${name}"
        value="${option/name}" checked="${option/selected}" />
      <label for="${name}-${option/name}">${option/value}</label>
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
            return [{'name': '1', 'value': '', 'is_selected': value}]

        # Case 3: Error
        raise ValueError, 'expected boolean or enumerate datatype'



class PathSelectorWidget(object):

    action = 'add_link'
    display_workflow = True

    template = make_stl_template("""
    <input type="text" id="selector-${name}" size="${size}" name="${name}"
      value="${value}" />
    <input id="selector-button-${name}" type="button" value="..."
      name="selector_button_${name}"
      onclick="popup(';${action}?target_id=selector-${name}&amp;mode=input', 620, 300);"/>
    ${workflow_state}""")


    def workflow_state(self):
        if self.display_workflow:
            path = self.datatype.encode(self.value)
            if path:
                context = get_context()
                resource = context.resource.get_resource(path, soft=True)
                if resource:
                    return get_workflow_preview(resource, context)

        return None



class ImageSelectorWidget(PathSelectorWidget):

    action = 'add_image'
    width = 128
    height = 128

    template = make_stl_template("""
    <input type="text" id="selector-${name}" size="${size}" name="${name}"
      value="${value}" />
    <input id="selector-button-${name}" type="button" value="..."
      name="selector_button_${name}"
      onclick="popup(';${action}?target_id=selector-${name}&amp;mode=input', 620, 300);" />
    ${workflow_state}
    <br/>
    <img src="${value}/;thumb?width=${width}&amp;height=${height}" stl:if="value"/>""")



###########################################################################
# Generate Form
###########################################################################
class AutoForm(STLForm):
    """Fields is a dictionnary:

      {'firstname': Unicode(mandatory=True),
       'lastname': Unicode(mandatory=True)}

    Widgets is a list:

      [TextInput('firstname', title=MSG(u'Firstname')),
       TextInput('lastname', title=MSG(u'Lastname'))]
    """

    template = 'auto_form.xml'
    submit_value = MSG(u'Save')
    submit_class = 'button-ok'
    description = None


    def fields(self):
        return [ x for x in self.get_fields() if issubclass(x, FormField) ]


    def first_field(self):
        return self.field_names[0]


    def form_action(self):
        return self.context.uri

