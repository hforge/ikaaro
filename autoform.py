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

# Import from the Standard Library
from random import randint

# Import from itools
from itools.core import get_abspath, thingy_lazy_property
from itools.datatypes import DataType, Date, Enumerate, Boolean, Unicode
from itools.fs import lfs
from itools.gettext import MSG, get_language_msg
from itools.html import stream_to_str_as_xhtml, stream_to_str_as_html
from itools.html import xhtml_doctype, sanitize_stream, stream_is_empty
from itools.stl import stl
from itools.web import STLForm, get_context
from itools.xml import XMLParser

# Import from ikaaro
from buttons import Button
from utils import CMSTemplate, make_stl_template



xhtml_namespaces = {None: 'http://www.w3.org/1999/xhtml'}



###########################################################################
# DataTypes
###########################################################################
class XHTMLBody(DataType):
    """Read and write XHTML.
    """
    sanitize_html = True

    def decode(cls, data):
        events = XMLParser(data, namespaces=xhtml_namespaces,
                           doctype=xhtml_doctype)
        if cls.sanitize_html is True:
            events = sanitize_stream(events)
        return list(events)


    @staticmethod
    def encode(value):
        if value is None:
            return ''
        return stream_to_str_as_xhtml(value)


    @staticmethod
    def is_empty(value):
        return stream_is_empty(value)



class HTMLBody(XHTMLBody):
    """TinyMCE specifics: read as XHTML, rendered as HTML.
    """

    @staticmethod
    def encode(value):
        if value is None:
            return ''
        return stream_to_str_as_html(value)



###########################################################################
# Widgets
###########################################################################

def get_default_widget(datatype):
    if issubclass(datatype, Boolean):
        return RadioWidget
    elif issubclass(datatype, Date):
        return DateWidget
    elif issubclass(datatype, Enumerate):
        return SelectWidget

    return TextWidget



class Widget(CMSTemplate):

    language = None
    maxlength = None
    size = None
    suffix = None
    tip = None
    type = 'text'
    # Focus on it if the first one displayed
    focus = True
    onsubmit = None

    template = make_stl_template("""
    <input type="${type}" id="${id}" name="${name}" value="${value}"
      maxlength="${maxlength}" size="${size}" />
      <label class="language" for="${id}" stl:if="language"
      >${language}</label>""")


    def __init__(self, name=None, **kw):
        if name:
            self.name = name
        self.id = self.name.replace('_', '-')



class TextWidget(Widget):

    size = 40



class HiddenWidget(Widget):

    type = 'hidden'
    focus = False



class FileWidget(Widget):

    type = 'file'



class PasswordWidget(Widget):

    type = 'password'



class ReadOnlyWidget(Widget):

    template = make_stl_template("""
    <input type="hidden" id="${id}" name="${name}" value="${value_}" />
    ${displayed_}""")

    displayed = None
    focus = False


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



class MultilineWidget(Widget):

    template = make_stl_template("""
    <label class="language block" for="${id}" stl:if="language"
      >${language}</label>
    <textarea rows="${rows}" cols="${cols}" id="${id}" name="${name}"
    >${value}</textarea>""")

    rows = 5
    cols = 60



class RadioWidget(Widget):

    template = make_stl_template("""
    <stl:block stl:repeat="option options">
      <input type="radio" id="${id}-${option/name}" name="${name}"
        value="${option/name}" checked="${option/selected}" />
      <label for="${id}-${option/name}">${option/value}</label>
      <br stl:if="not oneline" />
    </stl:block>""")

    oneline = False
    has_empty_option = True # Only makes sense for enumerates
                            # FIXME Do this other way


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
                options = datatype.get_namespace(value)
            else:
                options = value

            # Empty option
            if self.has_empty_option:
                options.insert(0,
                    {'name': '', 'value': '',  'selected': False})

            # Select first item if none selected
            for option in options:
                if option['selected'] is True:
                    return options

            if options:
                options[0]['selected'] = True
            return options

        # Case 2: Boolean
        if issubclass(datatype, Boolean):
            default_labels = {'yes': MSG(u'Yes'), 'no': MSG(u'No')}
            labels = getattr(self, 'labels', default_labels)
            yes_selected = value in [True, 1, '1']
            return [
                {'name': '1', 'value': labels['yes'], 'selected': yes_selected},
                {'name': '0', 'value': labels['no'],
                 'selected': not yes_selected}]

        # Case 3: Error
        err = 'datatype "%s" should be enumerate or boolean'
        raise ValueError, err % self.name



class CheckboxWidget(Widget):

    template = make_stl_template("""
    <stl:block stl:repeat="option options">
      <input type="checkbox" id="${id}-${option/name}" name="${name}"
        value="${option/name}" checked="${option/selected}" />
      <label for="${id}-${option/name}">${option/value}</label>
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
            return [{'name': '1', 'value': '',
                     'selected': value in [True, 1, '1']}]

        # Case 3: Error
        raise ValueError, 'expected boolean or enumerate datatype'



class SelectWidget(Widget):

    template = make_stl_template("""
    <select id="${id}" name="${name}" multiple="${multiple}" size="${size}"
      class="${css}">
      <option value="" stl:if="has_empty_option"></option>
      <option stl:repeat="option options" value="${option/name}"
        selected="${option/selected}">${option/value}</option>
    </select>""")


    css = None
    has_empty_option = True
    size = None


    def multiple(self):
        return self.datatype.multiple


    def options(self):
        value = self.value
        # Check whether the value is already a list of options
        # FIXME This is done to avoid a bug when using a select widget in an
        # auto-form, where the 'datatype.get_namespace' method is called
        # twice (there may be a better way of handling this).
        if type(value) is not list:
            return self.datatype.get_namespace(value)
        return value



class DateWidget(Widget):

    tip = MSG(u"Format: 'yyyy-mm-dd'")

    template = make_stl_template("""
    <input type="text" name="${name}" value="${value_}" id="${id}"
      class="dateField" size="${size}" />
    <button class="${css} button-selector">...</button>
    <script type="text/javascript">
      jQuery( "input.dateField" ).dynDateTime({
        ifFormat: "${format}",
        showsTime: ${show_time_js},
        timeFormat: "24",
        button: ".next()" });
    </script>""")


    css = None
    format = '%Y-%m-%d'
    size = 10
    show_time = False
    tip = MSG(u'Click on button "..." to choose a date.')

    def show_time_js(self):
        # True -> true for Javascript
        return 'true' if self.show_time else 'false'


    @thingy_lazy_property
    def value_(self):
        value = self.value
        if value is None:
            return ''

        # ['2007-08-01\r\n2007-08-02']
        if self.datatype.multiple and isinstance(value, list):
            return value[0]

        return value


    def dates(self):
        return self.value_.splitlines()



class DatetimeWidget(DateWidget):

    template = make_stl_template("""
    <input type="text" name="${name}" value="${value_}" id="${id}"
      class="dateField" size="10" />
    <button class="${css} button-selector">...</button>
    <input type="text" name="${name}_time" value="${value_time}" size="5" />
    <script type="text/javascript">
      jQuery( "input.dateField" ).dynDateTime({
        ifFormat: "${format}",
        timeFormat: "24",
        button: ".next()" });
    </script>""")


    @thingy_lazy_property
    def value_time(self):
        # FIXME A needed hack since this cannot be done properly with
        # ikaaro
        time = get_context().query['%s_time' % self.name]
        if time:
            return time.strftime('%H:%M')
        return ''



class PathSelectorWidget(TextWidget):

    action = 'add_link'
    display_workflow = True
    tip = MSG(u'Click on button "..." to select a file.')

    template = make_stl_template("""
    <input type="text" id="selector-${id}" size="${size}" name="${name}"
      value="${value}" />
    <button id="selector-button-${id}" class="button-selector"
      name="selector_button_${name}"
      onclick="return popup(';${action}?target_id=selector-${id}&amp;mode=input', 640, 480);">...</button>
    ${workflow_state}
    <label class="language" for="${id}" stl:if="language"
      >${language}</label>""")


    def workflow_state(self):
        from ikaaro.workflow import get_workflow_preview

        if self.display_workflow:
            value = self.value
            if type(value) is not str:
                value = self.datatype.encode(value)
            if value:
                context = get_context()
                resource = context.resource.get_resource(value, soft=True)
                if resource:
                    return get_workflow_preview(resource, context)

        return None



class ImageSelectorWidget(PathSelectorWidget):

    action = 'add_image'
    width = 128
    height = 128
    tip = MSG(u'Click on button "..." to select a file.')

    template = make_stl_template("""
    <input type="text" id="selector-${id}" size="${size}" name="${name}"
      value="${value}" />
    <button id="selector-button-${id}" class="button-selector"
      name="selector_button_${name}"
      onclick="return popup(';${action}?target_id=selector-${id}&amp;mode=input', 640, 480);">...</button>
    ${workflow_state}
    <label class="language" for="${id}" stl:if="language"
      >${language}</label>
    <br/>
    <img src="${value}/;thumb?width=${width}&amp;height=${height}" stl:if="value"/>""")



class RTEWidget(Widget):

    template = '/ui/tiny_mce/rte.xml'
    rte_css = ['/ui/aruni/style.css', '/ui/tiny_mce/content.css']
    scripts = [
        '/ui/tiny_mce/tiny_mce_src.js',
        '/ui/tiny_mce/javascript.js']

    # Configuration
    # See http://wiki.moxiecode.com/index.php/TinyMCE:Configuration
    width = None
    height = '340px'
    readonly = False
    # toolbar
    toolbar1 = ('newdocument,code,|,bold,italic,underline,strikethrough,|,'
                'justifyleft,justifycenter,justifyright, justifyfull,|,'
                'bullist,numlist,|, outdent, indent,|,undo,redo,|,link,'
                'unlink,image,media')
    toolbar2 = ('tablecontrols,|,nonbreaking,|,removeformat,forecolor,'
                'backcolor,|,formatselect')
    toolbar3 = None
    resizing = True
    plugins = 'safari,table,media,advimage,advlink,nonbreaking'
    # Extending the existing rule set.
    extended_valid_elements = None
    # css
    advanced_styles = None
    table_styles = None


    def rte_language(self):
        path = get_abspath('ui/tiny_mce/langs')
        languages = [ x[:-3] for x in lfs.get_names(path) ]
        return get_context().accept_language.select_language(languages)


    def css(self):
        return ','.join(self.rte_css)


    def resizing_js(self):
        return 'true' if self.resizing else 'false'


    def is_readonly(self):
        # True -> true for Javascript
        return 'true' if self.readonly else 'false'


    def get_prefix(self):
        context = get_context()
        here = context.resource.get_abspath()
        prefix = here.get_pathto(self.template)
        return prefix


    def render(self):
        prefix = self.get_prefix()
        template = self.get_template()
        return stl(events=template, namespace=self, prefix=prefix)



class CaptchaDatatype(Unicode):
    mandatory = True


    @staticmethod
    def is_valid(value):
        context = get_context()
        site_root = context.site_root
        answer = site_root.get_property('captcha_answer')
        return answer == value



class CaptchaWidget(TextWidget):
    title = MSG(u"Please answer the question below:")
    template = make_stl_template("""
    ${question}
    <input type="text" id="${id}" name="${name}" value="${value}"
      maxlength="${maxlength}" size="${size}" />""")


    def question(self):
        context = get_context()
        site_root = context.site_root
        return site_root.get_property('captcha_question')



class LocationWidget(SelectWidget):
    """This widget is only used in NewInstance forms. It is a hack because
    it is a composite widget and ikaaro does not allow to do this easily.
    """

    template = make_stl_template("""
    <select id="${id}" name="${name}" class="${css}">
      <option stl:repeat="option options" value="${option/name}"
        selected="${option/selected}">${option/value}</option>
    </select>
    <input stl:if="include_name"
      type="text" id="name" name="name" value="${name_value}"
      maxlength="80" size="40" style="width: 50%" />
    """)

    include_name = True

    def name_value(self):
        return get_context().query['name']



class ProgressBarWidget(Widget):
    name = 'progress-bar'
    onsubmit = 'startProgressBar();'

    template = make_stl_template("""
    <div id ="progress-bar-widget">
        <div id="attachment-file-infos">
            <p id="file-name" />
            <p id="file-size" />
            <p id="file-type" />
        </div>
        <div id="progress-bar-box">
            <span><div id="progress-bar"/></span><span id="percent"/>
            <div id="upload-size" />
        </div>
    </div>
    <script type="text/javascript">
      $('head').append('<link rel="stylesheet" href="/ui/progressbar/jquery-progressbar.css" type="text/css" />');
      var upload_id = ${upload_id};
      $("INPUT:file").focus(function () {
        attachmentSelected($(this));
      });
    </script>
    <script  type="text/javascript" src="/ui/progressbar/jquery-progressbar.min.js"/>
    """)


    def __init__(self, **kw):
        # An int in [1, 2^31 - 1]
        self.upload_id = str(randint(1, 2147483647))

        # HACK to add the upload_id in the POST URL
        context = get_context()
        if context is None:
            return
        context.uri = context.uri.replace(upload_id=self.upload_id)



###########################################################################
# Common widgets to reuse
###########################################################################
location_widget = LocationWidget('path', title=MSG(u'Location'))
title_widget = TextWidget('title', title=MSG(u'Title'))
description_widget = MultilineWidget('description',
                                     title=MSG(u'Description'), rows=8)
subject_widget = TextWidget('subject', title=MSG(u'Keywords'),
                            tip=MSG(u'Separated by comma'))
rte_widget = RTEWidget('data', title=MSG(u'Body'))
timestamp_widget = HiddenWidget('timestamp')
file_widget = FileWidget('file', title=MSG(u'Replace file'))


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
    template = '/ui/auto_form.xml'
    description = None
    actions = [Button(access=True, css='button-ok', title=MSG(u'Save'))]

    def get_widgets(self, resource, context):
        return self.widgets


    def get_actions(self, resource, context):
        return self.actions


    def _get_action_namespace(self, resource, context):
        # (1) Actions (submit buttons)
        actions = []
        for button in self.get_actions(resource, context):
            actions.append(button(resource=resource, context=context))
        return actions


    def get_namespace(self, resource, context):
        widgets_namespace = STLForm.get_namespace(self, resource, context)

        # Local Variables
        fields = self.get_schema(resource, context)
        widgets = self.get_widgets(resource, context)
        languages = resource.get_edit_languages(context)

        # Build widgets namespace
        first_widget = None
        onsubmit = None
        ns_widgets = []
        for widget in widgets:
            datatype = fields.get(widget.name, None)
            ns_widget = widgets_namespace.get(widget.name,
                                              {'name': widget.name,
                                               'value': None,
                                               'error': None})
            ns_widget['title'] = getattr(widget, 'title', None)
            ns_widget['id'] = widget.id
            ns_widget['mandatory'] = getattr(datatype, 'mandatory', False)
            ns_widget['is_date'] = (datatype is not None and
                                    issubclass(datatype, Date))
            ns_widget['suffix'] = widget.suffix
            ns_widget['tip'] = widget.tip
            ns_widget['endline'] = getattr(widget, 'endline', None)

            # onsubmit
            widget_onsubmit = getattr(widget, 'onsubmit', None)
            if widget_onsubmit is not None and onsubmit is not None:
                raise ValueError, "2 widgets want to change onsubmit"
            onsubmit = widget_onsubmit

            # multilingual or monolingual
            value = ns_widget['value']
            if getattr(datatype, 'multilingual', False):
                widgets_html = []
                for language in languages:
                    language_title = get_language_msg(language)
                    widget_name = '%s:%s' % (widget.name, language)
                    widgets_html.append(widget(name=widget_name,
                                               datatype=datatype,
                                               value=value[language],
                                               language=language_title))
                    if first_widget is None and widget.focus:
                        first_widget = widget_name
                # fix label
                if widgets_html:
                    ns_widget['name'] = widgets_html[0].name
            else:
                widget = widget(datatype=datatype, value=value)
                widgets_html = [widget]
                if first_widget is None and widget.focus:
                    first_widget = widget.name

            ns_widget['widgets'] = widgets_html
            ns_widgets.append(ns_widget)

        # Get the actions
        actions = self._get_action_namespace(resource, context)
        action = None
        if len(actions) == 1:
            # If one action, remove the value parameter
            # to simulate old functionment
            action = context.uri
            actions[0].name = None

        # Build namespace
        return {
            'before': None,
            'actions': actions,
            'action': action,
            'onsubmit': onsubmit,
            'title': self.get_title(context),
            'description': self.description,
            'first_widget': first_widget,
            'widgets': ns_widgets,
            'after': None}
