# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007-2008 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2008 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2011 Armel FORTUN <armel@tchack.com>
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
from itools.datatypes import Enumerate, DateTime, Time
from itools.gettext import MSG, get_language_msg
from itools.stl import stl
from itools.web import STLView

# Import from ikaaro
from buttons import Button
from datatypes import BirthDate
from datatypes import Days, Months, Years


###########################################################################
# Import widgets for backwards compatibility.
# TODO Remove sometime after 0.75
###########################################################################
from widgets import Widget, TextWidget, HiddenWidget, FileWidget
from widgets import PasswordWidget, ChoosePassword_Widget
from widgets import ReadOnlyWidget, MultilineWidget, RadioWidget
from widgets import CheckboxWidget, SelectWidget, DateWidget, DatetimeWidget
from widgets import PathSelectorWidget, ImageSelectorWidget
from widgets import BirthDateWidget, ColorPickerWidget, RTEWidget
from widgets import ProgressBarWidget, EditAreaWidget
from widgets import get_dynDateTime_scripts

from widgets import title_widget, description_widget, subject_widget
from widgets import timestamp_widget, file_widget, editarea_widget
from widgets import widgets_registry, get_default_widget



###########################################################################
# Generate Form
###########################################################################
class AutoForm(STLView):
    """Fields is a dictionnary:

      {'firstname': Unicode(mandatory=True),
       'lastname': Unicode(mandatory=True)}

    Widgets is a list:

      [TextWidget('firstname', title=MSG(u'Firstname')),
       TextWidget('lastname', title=MSG(u'Lastname'))]
    """

    template = '/ui/auto_form.xml'
    template_field = '/ui/auto_form_field.xml'

    form_id = None
    widgets = []
    description = None
    method = 'post'
    actions = [Button(access=True, css='button-ok', title=MSG(u'Save'))]

    def get_widgets(self, resource, context):
        return self.widgets


    def get_actions(self, resource, context):
        return self.actions


    def _get_action_namespace(self, resource, context):
        # Actions (submit buttons)
        return [ button(resource=resource, context=context)
                 for button in self.get_actions(resource, context) ]


    def get_scripts(self, context):
        scripts = []
        for widget in self.get_widgets(self.resource, context):
            for script in widget.scripts:
                if script not in scripts:
                    scripts.append(script)

        return scripts


    def get_styles(self, context):
        styles = []
        for widget in self.get_widgets(self.resource, context):
            for style in widget.styles:
                if style not in styles:
                    styles.append(style)
        return styles


    #########################
    # Hack for datatypes
    #########################
    def _get_form(self, resource, context):
        form = super(AutoForm, self)._get_form(resource, context)
        # Combine date & time
        for name, value in form.items():
            if type(value) is date:
                value_time = form.get('%s_time' % name)
                if value_time is not None:
                    value = datetime.combine(value, value_time)
                    form[name] = context.fix_tzinfo(value)
        # Hack for BirthDate
        schema = self.get_schema(resource, context)
        for name, datatype in schema.items():
            if issubclass(datatype, BirthDate):
                value_day = int(form.get('%s_day' % name))
                value_month = int(form.get('%s_month' % name))
                value_year = int(form.get('%s_year' % name))
                if value_day and value_month and value_year:
                    form[name] = date(value_year, value_month, value_day)
        return form


    def get_schema(self, resource, context):
        schema = super(AutoForm, self).get_schema(resource, context)
        # Hack for some Datatypes
        for name, datatype in schema.items():
            # Special case: datetime
            if issubclass(datatype, DateTime):
                schema['%s_time' % name] = Time
            # Special case: birthdate
            elif issubclass(datatype, BirthDate):
                schema['%s_day' % name] = Days
                schema['%s_month' % name] = Months
                schema['%s_year' % name] = Years
        return schema


    #########################
    # End hack for datatypes
    #########################

    def get_before_namespace(self, resource, context):
        return None


    def get_after_namespace(self, resource, context):
        return None


    def get_namespace(self, resource, context):
        namespace = super(AutoForm, self).get_namespace(resource, context)

        # Local Variables
        template = context.get_template(self.template_field)
        fields = self.get_schema(resource, context)
        languages = resource.get_edit_languages(context)

        # Build widgets namespace
        fields_list = []
        fields_dict = {}

        first_widget = None
        onsubmit = None
        for widget in self.get_widgets(resource, context):
            widget_name = widget.name
            datatype = fields.get(widget.name, None)
            field_ns = namespace.get(widget.name,
                                     {'name': widget.name, 'value': None,
                                      'error': None})
            field_ns['title'] = getattr(widget, 'title', None)
            field_ns['id'] = widget.id
            field_ns['mandatory'] = getattr(datatype, 'mandatory', False)
            field_ns['tip'] = widget.tip
            field_ns['endline'] = getattr(widget, 'endline', False)

            # onsubmit
            widget_onsubmit = getattr(widget, 'onsubmit', None)
            if widget_onsubmit is not None and onsubmit is not None:
                raise ValueError, "2 widgets want to change onsubmit"
            onsubmit = widget_onsubmit

            # Get value
            if self.method == 'get':
                value = context.get_query_value(widget.name, datatype)
                if issubclass(datatype, Enumerate):
                    value = datatype.get_namespace(value)
            else:
                value = field_ns['value']
                if is_prototype(datatype, DateTime) and len(value) <= 10:
                    value_time = namespace.get('%s_time' % widget.name,
                                               {'value': None})
                    value_time = value_time['value']
                    if value_time:
                        value += 'T%s' % value_time

            # multilingual or monolingual
            field_ns['widgets'] = widgets_html = []
            if getattr(datatype, 'multilingual', False):
                for language in languages:
                    language_title = get_language_msg(language)
                    widget = widget(name='%s:%s' % (widget_name, language),
                                    datatype=datatype,
                                    value=value[language],
                                    language=language_title)
                    widgets_html.append(widget)
                    if first_widget is None and widget.focus:
                        first_widget = widget.id
                # fix label
                if widgets_html:
                    field_ns['name'] = widgets_html[0].name
            else:
                widget = widget(datatype=datatype, value=value)
                widgets_html.append(widget)
                if first_widget is None and widget.focus:
                    first_widget = widget.id

            # Ok
            stream = stl(template, field_ns)
            fields_list.append(stream)
            fields_dict[widget_name] = stream

        # Enctype
        enctype = 'multipart/form-data' if self.method == 'post' else None
        # Get the actions
        actions = self._get_action_namespace(resource, context)

        # Before and after
        before = self.get_before_namespace(resource, context)
        after = self.get_after_namespace(resource, context)

        # Build namespace
        return {
            'form_id': self.form_id,
            'before': before,
            'actions': actions,
            'method': self.method,
            'enctype': enctype,
            'onsubmit': onsubmit,
            'title': self.get_title(context),
            'description': self.description,
            'first_widget': first_widget,
            'fields_list': fields_list,
            'fields': fields_dict,
            'after': after}
