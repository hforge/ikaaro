# -*- coding: UTF-8 -*-
# Copyright (C) 2011 Sylvain Taverne <sylvain@itaapy.com>
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
from itools.core import proto_lazy_property
from itools.datatypes import Enumerate
from itools.gettext import MSG

# Import from ikaaro
from ikaaro.autoform import SelectWidget, Widget
from ikaaro.fields import Integer_Field
from ikaaro.utils import make_stl_template


class Reminder_Unit(Enumerate):

    options = [{'name': 60, 'value': MSG(u'Minutes')},
               {'name': 3600, 'value': MSG(u'Hours')},
               {'name': 86400, 'value': MSG(u'Days')}]



class Reminder_Widget(Widget):
    """ Reminder interval (in seconds) is calculate thanks to javascript.
    XXX: That can be done without javascript with
    the same hack that DateTimeWidget
    """

    template = make_stl_template("""
    <input type="checkbox" id="${name}-checkbox"
      name="${name}-checbkox" checked="${has_remind}"/>
    <label for="${name}-checbkox">I want to be remind</label>
    <span id="${name}-area">
      <input type="hidden" name="${name}" value="${value}" id="${id}"/>
      <input type="text" name="${name}-number" value="${number_value}"
        size="3" id="${id}-number"/>
      ${reminders}
      before the event.
    </span>
    <script type="text/javascript">
      display_reminder();
      function calculate_seconds(){
        $("#${id}").val($("#${name}-number").val() * $("#${name}-unit").val());
      }
      function display_reminder(){
        if($("#${id}-checkbox:checked").length == 0){
          $("#${id}").val(0);
          $("#${name}-area").hide();
        }else{
          calculate_seconds();
          $("#${name}-area").show();
        }
      }
      $("#${id}-checkbox").change(function(){
        display_reminder();
      });
      $("#${id}-number").change(function(){
        calculate_seconds();
      });
      $("#${id}-unit").change(function(){
        calculate_seconds();
      });
    </script>
    """)

    @proto_lazy_property
    def has_remind(self):
        if not self.value:
            return None
        return int(self.value) > 0


    @proto_lazy_property
    def number_value(self):
        if not self.value:
            return 10
        return int(self.value) / self.reminder_value



    @proto_lazy_property
    def reminder_value(self):
        if not self.value:
            return None
        value = int(self.value)
        if value >= 86400:
            return 86400
        elif value >= 3600:
            return 3600
        return 60


    @proto_lazy_property
    def reminders(self):
        return SelectWidget('%s-unit' % self.name, value=self.reminder_value,
                            datatype=Reminder_Unit, has_empty_option=False)



class Reminder_Field(Integer_Field):

    widget = Reminder_Widget
