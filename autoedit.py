# -*- coding: UTF-8 -*-
# Copyright (C) 2010 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2010-2011 Henry Obein <henry@itaapy.com>
# Copyright (C) 2010-2011 Taverne Sylvain <sylvain@itaapy.com>
# Copyright (C) 2011 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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

# Import from the Standard Library
from datetime import datetime, date

# Import from itools
from itools.core import is_prototype
from itools.datatypes import DateTime, Time, String, URI
from itools.gettext import MSG
from itools.i18n import get_language_name
from itools.uri import Reference
from itools.web import get_context

# Import from ikaaro
from autoform import AutoForm, HiddenWidget
from autoform import timestamp_widget
from datatypes import BirthDate
from datatypes import Days, Months, Years
from fields import Field
import messages
from views import ContextMenu


class EditLanguageMenu(ContextMenu):

    title = MSG(u'Configuration')
    template = '/ui/generic/edit_language_menu.xml'
    view = None

    def action(self):
        uri = self.context.uri
        return Reference(uri.scheme, uri.authority, uri.path, {}, None)


    def get_fields(self):
        context = self.context
        resource = self.resource
        view = self.view

        widgets = view._get_widgets(resource, context)
        # Build widgets list
        fields, to_keep = view._get_query_fields(resource, context)

        return [ {'name': widget.name,
                  'title': getattr(widget, 'title', 'name'),
                  'selected': widget.name in fields}
                 for widget in widgets if widget.name not in to_keep ]


    def fields(self):
        items = self.get_fields()
        # Defaults
        for item in items:
            for name in ['class', 'src', 'items']:
                item.setdefault(name, None)

        return items


    def _get_items(self):
        multilingual = False
        schema = self.view._get_schema(self.resource, self.context)
        for key, datatype in schema.iteritems():
            if getattr(datatype, 'multilingual', False):
                multilingual = True
                break

        if multilingual is False:
            # No multilingual fields
            return []

        root = self.resource.get_root()
        languages = root.get_value('website_languages')
        edit_languages = self.resource.get_edit_languages(self.context)
        return [ {'title': get_language_name(x), 'name': x,
                  'selected': x in edit_languages}
                 for x in languages ]


    def get_items(self):
        """Do not return item if unique."""
        items = self._get_items()
        if len(items) == 1:
            return []
        return items


    def get_hidden_fields(self):
        return self.view._get_query_to_keep(self.resource, self.context)


    def hidden_fields(self):
        return self.get_hidden_fields()


    def display(self):
        """Do not display the form is there is nothing to show"""
        items = self.get_items()
        if len(items):
            return True
        fields = self.get_fields()
        if len(fields):
            return True
        return len(self.hidden_fields())



class AutoEdit(AutoForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit')

    fields = ['title', 'description', 'subject']
    def get_fields(self):
        context = self.context
        resource = self.resource

        for name in self.fields:
            field = self.get_field(resource, name)
            if not is_prototype(field, Field):
                field = resource.get_field(name)

            if not field:
                continue

            # Access control
            if field.access('write', resource):
                yield name


    def get_field(self, resource, name):
        field = getattr(self, name, None)
        if field is not None and is_prototype(field, Field):
            return field
        return resource.get_field(name)


    context_menus = []
    def get_context_menus(self):
        context_menus = self.context_menus[:] # copy
        context_menus.append(EditLanguageMenu(view=self))
        return context_menus


    #######################################################################
    # GET
    #######################################################################
    def get_query_schema(self):
        context = get_context()
        resource = context.resource

        schema = self._get_schema(resource, context)
        for name, datatype in schema.items():
            if getattr(datatype, 'mandatory', False) is True:
                schema[name] = datatype(mandatory=False)

        return schema


    # XXX method name sucks
    def _get_query_to_keep(self, resource, context):
        """Return a list of dict {'name': name, 'value': value}"""
        return []


    def _get_query_fields(self, resource, context):
        """Return query fields and readonly or mandatory fields
        """
        schema = self._get_schema(resource, context)
        default = set()
        to_keep = set()

        for key, datatype in schema.iteritems():
            if getattr(datatype, 'hidden_by_default', False):
                continue
            # Keep readonly and mandatory widgets
            if getattr(datatype, 'mandatory', False):
                to_keep.add(key)
            if getattr(datatype, 'readonly', False):
                to_keep.add(key)
            default.add(key)
        fields = context.get_query_value('fields', type=String(multiple=True),
                                         default=default)
        return set(fields), to_keep


    def _get_datatype(self, resource, context, name):
        field = self.get_field(resource, name)
        if field is None:
            field = resource.get_field(name)
        field = field(resource=resource) # bind
        return field.get_datatype()


    def _get_schema(self, resource, context):
        schema = {'timestamp': DateTime(readonly=True),
                  'referrer': URI}

        # Add schema from the resource
        for name in self.get_fields():
            datatype = self._get_datatype(resource, context, name)

            # Special case: datetime
            if issubclass(datatype, DateTime):
                schema['%s_time' % name] = Time
            # Special case: birthdate
            elif issubclass(datatype, BirthDate):
                schema['%s_day' % name] = Days
                schema['%s_month' % name] = Months
                schema['%s_year' % name] = Years

            # Standard case
            schema[name] = datatype

        return schema


    def get_schema(self, resource, context):
        """Return reduced schema
           i.e. schema without 'hidden by default' datatypes.
        """
        base_schema = self._get_schema(resource, context)
        fields, to_keep = self._get_query_fields(resource, context)
        schema = {}
        for key in fields | to_keep:
            schema[key] = base_schema[key]

        return schema


    def _get_widget(self, resource, context, name):
        field = self.get_field(resource, name)
        if field is None:
            field = resource.get_field(name)
        return field.get_widget(name)


    def _get_widgets(self, resource, context):
        widgets = [timestamp_widget,
                   HiddenWidget('referrer')]
        for name in self.get_fields():
            widget = self._get_widget(resource, context, name)
            widgets.append(widget)

        return widgets


    def get_widgets(self, resource, context):
        """Return reduced widgets
           i.e. skip hide by default widgets.
        """
        base_widgets = self._get_widgets(resource, context)
        fields, to_keep = self._get_query_fields(resource, context)

        # Reduce widgets
        return [ widget for widget in base_widgets
                 if widget.name in fields or widget.name in to_keep ]


    def get_value(self, resource, context, name, datatype):
        # Timestamp
        if name == 'timestamp':
            return context.timestamp
        elif name == 'referrer':
            referrer = context.query.get('referrer')
            return referrer or context.get_referrer()

        # Datetime
        if name[-5:] == '_time' and issubclass(datatype, Time):
            value = self.get_value(resource, context, name[:-5], DateTime)
            if type(value) is not datetime:
                return None
            return value.time()
        # BirthDate
        elif name[-4:] == '_day' and issubclass(datatype, Days):
            value = self.get_value(resource, context, name[:-4], BirthDate)
            if type(value) is not date:
                return None
            value = str(value.day)
            context.query[name] = value
            return value
        elif name[-6:] == '_month' and issubclass(datatype, Months):
            value = self.get_value(resource, context, name[:-6], BirthDate)
            if type(value) is not date:
                return None
            value = str(value.month)
            context.query[name] = value
            return value
        elif name[-5:] == '_year' and issubclass(datatype, Years):
            value = self.get_value(resource, context, name[:-5], BirthDate)
            if type(value) is not date:
                return None
            value = str(value.year)
            context.query[name] = value
            return value

        # Standard
        if not getattr(datatype, 'multilingual', False):
            return resource.get_value(name)

        # Multilingual
        value = {}
        for language in resource.get_edit_languages(context):
            value[language] = resource.get_value(name, language=language)
        return value


    #######################################################################
    # POST
    #######################################################################
    def check_edit_conflict(self, resource, context, form):
        context.edit_conflict = False

        timestamp = form['timestamp']
        if timestamp is None:
            context.message = messages.MSG_EDIT_CONFLICT
            context.edit_conflict = True
            return

        mtime = resource.get_value('mtime')
        if mtime is not None and timestamp < mtime:
            # Conflict unless we are overwriting our own work
            last_author = resource.get_value('last_author')
            if last_author != context.user.name:
                user = context.root.get_user_title(last_author)
                context.message = messages.MSG_EDIT_CONFLICT2(user=user)
                context.edit_conflict = True


    def set_value(self, resource, context, name, form):
        """Return True if an error occurs otherwise False. If an error
        occurs, the context.message must be an ERROR instance.
        """
        if name.endswith(('_time', '_year', '_day', '_month', 'referrer')):
            return False
        value = form[name]
        if type(value) is dict:
            for language, data in value.iteritems():
                resource.set_value(name, data, language=language)
        else:
            resource.set_value(name, value)
        return False


    action_goto = None
    action_msg = messages.MSG_CHANGES_SAVED
    def action(self, resource, context, form):
        # Check edit conflict
        self.check_edit_conflict(resource, context, form)
        if context.edit_conflict:
            return

        # Get submit field names
        schema = self._get_schema(resource, context)
        fields, to_keep = self._get_query_fields(resource, context)

        # Save changes
        for key in fields | to_keep:
            datatype = schema[key]
            if getattr(datatype, 'readonly', False):
                continue
            if self.set_value(resource, context, key, form):
                return

        # Notify
        from cc import Observable
        if isinstance(resource, Observable):
            resource.notify_subscribers(context)

        # Ok
        if self.action_goto:
            return context.come_back(self.action_msg, goto=self.action_goto)
        context.message = self.action_msg
