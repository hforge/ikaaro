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

# Import from standard library
from operator import itemgetter

# Import from itools
from itools.core import merge_dicts
from itools.datatypes import Enumerate, String
from itools.gettext import MSG
from itools.web import ERROR, get_context
from itools.xml import XMLParser

# Import from ikaaro
from ikaaro.autoadd import AutoAdd
from ikaaro.autoedit import AutoEdit
from ikaaro.buttons import Button, BrowseButton
from ikaaro.exceptions import ConsistencyError
from ikaaro.fields import Char_Field, Color_Field, Owner_Field
from ikaaro.messages import MSG_NEW_RESOURCE, MSG_CHANGES_SAVED
from ikaaro.resource_ import DBResource
from ikaaro.views import BrowseForm


class Calendars_Enumerate(Enumerate):

    def get_options(self):
        context = get_context()
        calendars = context.search(format=Calendar.class_id).get_resources()
        options = [ {'name': str(x.abspath), 'value': x.get_title(),
                  'color': x.get_value('color')}
                 for x in calendars
                 if context.user.name not in x.get_value('hidden_for_users')]
        options.sort(key=itemgetter('value'))
        return options


#####################################
# Calendar views
#####################################

class AddButton(Button):

    access = True
    title = MSG(u'Create a new calendar...')
    name = 'add'
    css = 'button-add'


class UpdateCalendarVisibility(BrowseButton):

    access = 'is_allowed_to_view'
    css = 'button-ok'
    name = 'update_calendar_visibility'
    title = MSG(u'Update calendar visibility')



class Calendars_View(BrowseForm):

    title = MSG(u'Calendars')
    access = 'is_allowed_to_view'

    styles = ['/ui/agenda/style.css']

    schema = {'ids': String(multiple=True)}
    query_schema = merge_dicts(BrowseForm.query_schema,
                               sort_by=String(default='title'))

    can_be_open_in_fancybox = True
    search_widgets = []
    search_schema = {}

    table_actions = [UpdateCalendarVisibility, AddButton]
    table_columns = [
        ('checkbox', None),
        ('color', MSG(u'Color'), None),
        ('title', MSG(u'Title')),
        ('visible', MSG(u'Visible ?'), None),
        ]


    def get_items(self, resource, context):
        return context.search(format='calendar')


    def get_item_value(self, resource, context, item, column):
        if column in ('checkbox', 'visible'):
            hidden_for_users = item.get_value('hidden_for_users')
            visible = context.user.name not in hidden_for_users
            if column == 'checkbox':
                return item.abspath, visible
            return MSG(u'Yes') if visible else MSG(u'No')
        elif column == 'color':
            color = item.get_value('color')
            data = """
              <div class="calendar-family-color"
                style="background-color:{color}"/>"""
            return XMLParser(data.format(color=color))
        elif column == 'title':
            return item.get_title(), item.abspath
        proxy = super(Calendars_View, self)
        return proxy.get_item_value(resource, context, item, column)


    def action_update_calendar_visibility(self, resource, context, form):
        for calendar in self.get_items(resource, context).get_resources():
            if str(calendar.abspath) not in form['ids']:
                hidden_for_users = calendar.get_value('hidden_for_users')
                if context.user.name not in hidden_for_users:
                    calendar.set_value('hidden_for_users', context.user.name)
            else:
                hidden_for_users = calendar.get_value('hidden_for_users')
                if context.user.name in hidden_for_users:
                    hidden_for_users.remove(context.user.name)
                    calendar.set_value('hidden_for_users', hidden_for_users)
        # Ok
        context.message = MSG_CHANGES_SAVED


    def sort_and_batch(self, resource, context, results):
        # TODO BrowseForm should be able to sort items ?
        start = context.query['batch_start']
        size = context.query['batch_size']
        sort_by = context.query['sort_by']
        reverse = context.query['reverse']
        items = results.get_resources(sort_by=sort_by, reverse=reverse,
                                      start=start, size=size)
        return list(items)


    action_add_schema = {}
    def action_add(self, resource, context, form):
        goto = './;new_resource?type=calendar'
        return context.come_back(None, goto=goto)



class Calendar_Edit(AutoEdit):

    can_be_open_in_fancybox = True
    actions = [Button(access=True, css='button-ok', title=MSG(u'Save')),
               Button(access='is_allowed_to_remove',
                      name='remove', css='button-delete',
                      title=MSG(u'Remove this calendar'))]

    def action(self, resource, context, form):
        # Check edit conflict
        self.check_edit_conflict(resource, context, form)
        if context.edit_conflict:
            return
        super(Calendar_Edit, self).action(resource, context, form)
        return context.come_back(MSG_CHANGES_SAVED, goto='./;calendars')


    def action_remove(self, resource, context, form):
        # Remove resource
        try:
            resource.parent.del_resource(resource.name)
        except ConsistencyError:
            context.message = ERROR(u"Can't remove this calendar")
            return
        msg = MSG(u'This calendar has been removed')
        return context.come_back(msg, goto='./;calendars')



class Calendar_NewInstance(AutoAdd):

    automatic_resource_name = True
    can_be_open_in_fancybox = True

    def action(self, resource, context, form):
        child = self.make_new_resource(resource, context, form)
        if child is None:
            return
        # Ok
        return context.come_back(MSG_NEW_RESOURCE, goto='./;calendars')



#####################################
# Calendar
# A calendar contains events
#####################################

class Calendar(DBResource):

    class_id = 'calendar'
    class_title = MSG(u'Calendar')
    class_views = ['edit']

    # Fields
    title = DBResource.title(required=True)
    hidden_for_users = Char_Field(multiple=True)
    color = Color_Field(title=MSG(u'Color'), default='#0467BA', required=True)
    owner = Owner_Field

    # Views
    _fields = ['title', 'color']
    new_instance = Calendar_NewInstance(fields=_fields)
    edit = Calendar_Edit(fields=_fields)
