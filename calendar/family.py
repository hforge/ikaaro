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
from itools.datatypes import Enumerate
from itools.gettext import MSG
from itools.web import get_context
from itools.xml import XMLParser

# Import from ikaaro
from ikaaro.autoadd import AutoAdd
from ikaaro.autoedit import AutoEdit
from ikaaro.buttons import RemoveButton
from ikaaro.fields import Char_Field
from ikaaro.folder_views import Folder_BrowseContent
from ikaaro.messages import MSG_NEW_RESOURCE
from ikaaro.resource_ import DBResource



class Calendar_FamiliesEnumerate(Enumerate):

    def get_options(self):
        calendar = get_context().root.get_resource('config/calendar')
        return [ {'name': str(family.abspath), 'value': family.get_title(),
                  'color': family.get_value('color')}
                 for family in calendar.search_resources(cls=Calendar_Family)]



class Families_View(Folder_BrowseContent):

    title = MSG(u'Families')

    depth = 1

    search_widgets = []
    search_schema = {}

    table_actions = [RemoveButton]
    table_columns = [
        ('checkbox', None),
        ('icon', None),
        ('title', MSG(u'Title')),
        ('color', MSG(u'Color'))]


    base_classes = ('calendar-family',)


    def get_item_value(self, resource, context, item, column):
        if column == 'title':
            return item.get_title(), item.name
        elif column == 'color':
            color = item.get_value('color')
            data = '<span style="color:{color}">{color}</span>'
            return XMLParser(data.format(color=color))
        proxy = super(Families_View, self)
        return proxy.get_item_value(resource, context, item, column)



class Calendar_Family_NewInstance(AutoAdd):

    automatic_resource_name = True

    def action(self, resource, context, form):
        child = self.make_new_resource(resource, context, form)
        if child is None:
            return
        # Ok
        return context.come_back(MSG_NEW_RESOURCE, goto='./;families')



class Calendar_Family(DBResource):

    class_id = 'calendar-family'
    class_title = MSG(u'Calendar family')
    class_views = ['edit']

    # Fields
    fields = DBResource.fields + ['color']
    color = Char_Field(title=MSG(u'Color'))

    # Views
    _fields = ['title', 'color']
    new_instance = Calendar_Family_NewInstance(fields=_fields)
    edit = AutoEdit(fields=_fields)
