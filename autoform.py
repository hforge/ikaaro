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
from itools.core import thingy_lazy_property
from itools.datatypes import Date, Enumerate, Boolean
from itools.gettext import MSG
from itools.stl import make_stl_template
from itools.web import stl_view
from itools.web import boolean_field, choice_field, hidden_field
from itools.web import readonly_field, text_field

# Import from ikaaro
from fields import DateField



def get_default_field(datatype):
    if issubclass(datatype, Boolean):
        return boolean_field
    elif issubclass(datatype, Date):
        return DateField
    elif issubclass(datatype, Enumerate):
        return choice_field

    return text_field



class PathSelectorWidget(object):

    action = 'add_link'
    display_workflow = True

    template = make_stl_template("""
    <input type="text" id="selector-${id}" size="${size}" name="${name}"
      value="${value}" />
    <input id="selector-button-${id}" type="button" value="..."
      name="selector_button_${name}"
      onclick="popup(';${action}?target_id=selector-${id}&amp;mode=input', 620, 300);"/>
    ${workflow_state}""")


    def workflow_state(self):
        if self.display_workflow:
            value = self.value
            if type(value) is not str:
                value = self.datatype.encode(value)
            if value:
                resource = self.resource.get_resource(value, soft=True)
                if resource:
                    return resource.get_workflow_preview()

        return None



class ImageSelectorWidget(PathSelectorWidget):

    action = 'add_image'
    width = 128
    height = 128

    template = make_stl_template("""
    <input type="text" id="selector-${id}" size="${size}" name="${name}"
      value="${value}" />
    <input id="selector-button-${id}" type="button" value="..."
      name="selector_button_${name}"
      onclick="popup(';${action}?target_id=selector-${id}&amp;mode=input', 620, 300);" />
    ${workflow_state}
    <br/>
    <img src="${value}/;thumb?width=${width}&amp;height=${height}" stl:if="value"/>""")



###########################################################################
# Generate Form
###########################################################################
class AutoForm(stl_view):
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
    view_description = None


    @thingy_lazy_property
    def content_language(self):
        return self.resource.get_content_language()


    @thingy_lazy_property
    def fields(self):
        return [ x for x in self.get_fields()
                 if issubclass(x, hidden_field) and x.source == 'form']


    @thingy_lazy_property
    def hidden_fields(self):
        return [ x for x in self.fields if not issubclass(x, readonly_field) ]


    @thingy_lazy_property
    def visible_fields(self):
        return [ x for x in self.fields if issubclass(x, readonly_field) ]


    def first_field(self):
        return self.visible_fields[0].name


    def form_action(self):
        return self.context.uri

