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
from datetime import datetime
from operator import itemgetter
from os.path import basename
from random import randint
from urllib import quote

# Import from itools
from itools.core import freeze, get_abspath
from itools.core import proto_property, proto_lazy_property
from itools.datatypes import Boolean, Email, Enumerate, PathDataType, String
from itools.datatypes import Date, DateTime
from itools.fs import lfs
from itools.gettext import MSG
from itools.handlers import Image
from itools.stl import stl
from itools.web import BaseView, get_context

# Import from ikaaro
from datatypes import Password_Datatype
from datatypes import Days, Months, Years
from utils import CMSTemplate, make_stl_template



class Widget(CMSTemplate):

    id = None
    name = None
    language = None
    maxlength = None
    size = None
    tip = None
    type = 'text'
    focus = True # Focus on it if the first one displayed
    onsubmit = None
    css = None
    scripts = freeze([])
    styles = freeze([])

    template = make_stl_template("""
    <input type="${type}" id="${id}" name="${name}" value="${value}"
      maxlength="${maxlength}" size="${size}" class="${css}"/>
      <label class="language" for="${id}" stl:if="language"
      >${language}</label>""")


    def __init__(self, name=None, **kw):
        if name:
            self.name = name
        if self.name and not self.id:
            id = self.name
            self.id = id.replace('_', '-').replace(':', '-')



class TextWidget(Widget):

    size = 40



class HiddenWidget(Widget):

    type = 'hidden'
    focus = False



class FileWidget(Widget):

    title = MSG(u'File')

    template = make_stl_template("""
    <input type="file" id="${id}" name="${name}" maxlength="${maxlength}"
      size="${size}" class="${css}" />
    <label class="language" for="${id}" stl:if="language" >${language}</label>
    <br/>
    <img src=";get_image?name=${name}&amp;width=${width}&amp;height=${height}&amp;fit=${fit}"
      stl:if="thumb"/>""")

    width = 128
    height = 128
    fit = 1

    def thumb(self):
        return isinstance(self.value, Image)



class PasswordWidget(Widget):

    type = 'password'



class ChoosePassword_Widget(Widget):
    """Include a js password strength meter.
    """

    title = MSG(u'Password')

    template = make_stl_template("""
    <input type="password" id="${id}" name="${name}" maxlength="${maxlength}"
      size="${size}" class="${css}"/>
    <script type="text/javascript">
      jQuery( "#${id}" ).passStrength({
        userid: "#${userid}"
      });
    </script>""")

    @proto_property
    def scripts(self):
        context = get_context()
        handler = context.get_template('/ui/js/password_strength_plugin.js')
        return ['/ui/js/%s' % basename(handler.key)]

    # Password meter configuration
    userid = None



class ReadOnlyWidget(Widget):

    template = make_stl_template("""
    <input type="hidden" id="${id}" name="${name}" value="${value_}" />
    ${displayed_}""")

    displayed = None
    focus = False


    @proto_lazy_property
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
      class="${css}">${value_}</textarea>""")

    rows = 5
    cols = 60

    @proto_lazy_property
    def value_(self):
        value = self.value
        if type(value) is str:
            return value
        return value.to_str()



class RadioWidget(Widget):

    template = make_stl_template("""
    <stl:block stl:repeat="option options">
      <input type="radio" id="${id}-${option/name}" name="${name}"
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
                options = datatype.get_namespace(value)
            else:
                options = value

            # Select item if there is only one
            if len(options) == 1:
                options[0]['selected'] = True

            return options

        # Case 2: Boolean
        if issubclass(datatype, Boolean):
            default_labels = {'yes': MSG(u'Yes'), 'no': MSG(u'No')}
            labels = getattr(self, 'labels', default_labels)
            yes_selected = value in [True, 1, '1']
            return [
                {'name': '1', 'value': labels['yes'],
                 'selected': yes_selected},
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
    label = MSG(u'Yes')


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
            return [{'name': '1', 'value': self.label,
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


def get_dynDateTime_scripts():
    context = get_context()
    scripts = []
    # Calendar (http://code.google.com/p/dyndatetime/)
    scripts.append('/ui/js_calendar/jquery.dynDateTime.pack.js')
    languages = [
        'af', 'al', 'bg', 'br', 'ca', 'da', 'de', 'du', 'el', 'en', 'es',
        'fi', 'fr', 'hr', 'hu', 'it', 'jp', 'ko', 'lt', 'lv', 'nl', 'no',
        'pl', 'pt', 'ro', 'ru', 'si', 'sk', 'sp', 'sv', 'tr', 'zh']
    accept = context.accept_language
    language = accept.select_language(languages)
    if language is None:
        language = 'en'
    scripts.append('/ui/js_calendar/lang/calendar-%s.js' % language)
    return scripts


class DateWidget(Widget):

    template = make_stl_template("""
    <input type="text" name="${name}" value="${value_}" id="${id}"
      class="dateField" size="${size}" />
    <button class="${css} button-selector button-selector-agenda">...</button>
    <script type="text/javascript">
      jQuery( "input#${id}" ).dynDateTime({
        ifFormat: "${format}",
        showsTime: ${show_time_js},
        timeFormat: "24",
        button: ".next()" });
    </script>""")

    styles = ['/ui/js_calendar/calendar-aruni.css']

    css = None
    format = '%Y-%m-%d'
    size = 10
    show_time = False
    tip = MSG(u'Click on button "..." to choose a date (Format: "yyyy-mm-dd").')

    @proto_lazy_property
    def scripts(self):
        return get_dynDateTime_scripts()


    def show_time_js(self):
        # True -> true for Javascript
        return 'true' if self.show_time else 'false'


    @proto_lazy_property
    def value_(self):
        value = self.value
        if value is None:
            return ''

        # ['2007-08-01\r\n2007-08-02']
        if self.datatype.multiple and isinstance(value, list):
            value = value[0]
        if type(value) is not str:
            return value.strftime(self.format)
        return value


    def dates(self):
        return self.value_.splitlines()



class DatetimeWidget(DateWidget):

    template = make_stl_template("""
    <input type="text" name="${name}" value="${value_date}" id="${id}"
      class="dateField" size="10" maxlength="10"/>
    <button class="${css} button-selector button-selector-agenda">...</button>
    <input type="text" id="${id}-time" name="${name}_time"
      value="${value_time}" size="5" maxlength="5"/>
    <script type="text/javascript">
      jQuery( "input.dateField" ).dynDateTime({
        ifFormat: "${format}",
        timeFormat: "24",
        button: ".next()" });
        $("input[name=${name}_time]").mask("99:99");
        $("input[name=${name}_time]").val("${value_time}");
    </script>""")

    styles = ['/ui/js_calendar/calendar-aruni.css']

    @proto_lazy_property
    def scripts(self):
        return (['/ui/jquery.maskedinput-1.3.min.js'] +
                get_dynDateTime_scripts())


    @proto_lazy_property
    def value_(self):
        value = self.value
        if value is None:
            return '', ''

        try:
            value = self.datatype.decode(value)
        except StandardError:
            # XXX Heuristic here
            from itools.web import get_context
            context = get_context()
            return (context.get_form_value(self.name),
                    context.get_form_value('%s_time' % self.name))

        if type(value) is datetime:
            value_date = value.date()
            value_time = value.time()
        else:
            value_date = value
            value_time = self.value_time_default
            if value_time is None:
                return Date.encode(value_date), ''

        return Date.encode(value_date), value_time.strftime('%H:%M')


    @proto_lazy_property
    def value_date(self):
        return self.value_[0]



    value_time_default = None

    @proto_lazy_property
    def value_time(self):
        return self.value_[1]



class PathSelectorWidget(TextWidget):

    action = 'add_link'
    tip = MSG(u'Click on button "..." to select a file.')

    template = make_stl_template("""
    <input type="text" id="selector-${id}" size="${size}" name="${name}"
      value="${value}" />
    <button id="selector-button-${id}" class="button-selector button-selector-path"
      name="selector_button_${name}"
      onclick="return popup(';${action}?target_id=selector-${id}&amp;mode=input', 640, 480);">...</button>
    <label class="language" for="${id}" stl:if="language"
      >${language}</label>""")



class ImageSelectorWidget(PathSelectorWidget):

    action = 'add_image'
    width = 128
    height = 128
    tip = MSG(u'Click on button "..." to select a file.')

    template = make_stl_template("""
    <input type="text" id="selector-${id}" size="${size}" name="${name}"
      value="${value}" />
    <button id="selector-button-${id}" class="button-selector button-selector-image"
      name="selector_button_${name}"
      onclick="return popup(';${action}?target_id=selector-${id}&amp;mode=input', 640, 480);">...</button>
    <label class="language" for="${id}" stl:if="language"
      >${language}</label>
    <br/>
    <img src="${value}/;thumb?width=${width}&amp;height=${height}" stl:if="value"/>""")



class BirthDateWidget(Widget):

    template = make_stl_template("""
        ${year} ${month} ${day}
        <input type="hidden" name="${name}" value="1900-01-01"/>
         """)

    def get_widget(self, widget_name, datatype, value=None):
        context = get_context()
        name = '%s_%s' % (self.name, widget_name)
        value = context.get_form_value(name)
        if value is None and context.query.has_key(name):
            value = context.query.get(name)
        return SelectWidget(name=name, datatype=datatype, value=value,
                            has_empty_option=False).render()


    def day(self):
        return self.get_widget('day', Days)


    def month(self):
        return self.get_widget('month', Months)


    def year(self):
        return self.get_widget('year', Years)



class ColorPickerWidget(TextWidget):

    template = make_stl_template("""
    <div id="${id}-picker" />
    <input type="${type}" id="${id}" name="${name}" value="${value}"
      maxlength="${maxlength}" size="${size}" class="${css}"/>
    <label class="language" for="${id}" stl:if="language">${language}</label>
    <script>
      $(document).ready(function() {
        $('#${id}-picker').farbtastic('#${id}');
      });
    </script>""")

    scripts = ['/ui/js/farbtastic/farbtastic.js']
    styles = ['/ui/js/farbtastic/farbtastic.css']



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
        return get_context().resource.abspath.get_pathto(self.template)


    def render(self):
        prefix = self.get_prefix()
        template = self.get_template()
        return stl(events=template, namespace=self, prefix=prefix)



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
      var upload_id = ${upload_id};
      $("INPUT:file").focus(function () {
        attachmentSelected($(this));
      });
    </script>
    """)
    scripts = ['/ui/progressbar/jquery-progressbar.min.js']
    styles = ['/ui/progressbar/jquery-progressbar.css']


    def __init__(self, name=None, **kw):
        # An int in [1, 2^31 - 1]
        self.upload_id = str(randint(1, 2147483647))

        # HACK to add the upload_id in the POST URL
        context = get_context()
        if context is None:
            return
        context.uri = context.uri.replace(upload_id=self.upload_id)



class EditAreaWidget(MultilineWidget):
    """It's an EditArea Widget, for file code edit, used for edit the CSS here,
    see original code here: <http://www.cdolivet.com>"""

    template = '/ui/editarea/ea.xml'
    scripts = ['/ui/editarea/edit_area_full.js']

    # Configuration
    width = 610
    height = 340
    readonly = False


    def ea_language(self):
        path = get_abspath('ui/editarea/langs')
        languages = [ x[:-3] for x in lfs.get_names(path) ]
        return get_context().accept_language.select_language(languages)


    def get_prefix(self):
        context = get_context()
        here = context.resource.abspath
        prefix = here.get_pathto(self.template)
        return prefix


    def render(self):
        prefix = self.get_prefix()
        template = self.get_template()
        return stl(events=template, namespace=self, prefix=prefix)



###########################################################################
# Common widgets to reuse
###########################################################################
class GetFolders(BaseView):
    """ Get folders within a folder (combined with ajax).
    """
    access = 'is_allowed_to_view'
    query_schema = {'level0': String, 'level1': String, 'level2': String,
                    'level3': String, 'level4': String}

    def GET(self, resource, context):
        context.set_content_type('text/plain')

        query = context.query
        for key in ('level4', 'level3', 'level2', 'level1', 'level0'):
            value = query[key]
            if value:
                r_value = resource.get_resource(value, soft=True)
                if r_value:
                    options = []
                    for r_c in r_value.search_resources(format='folder'):
                        c = r_c.name
                        c_path = value + '/' + c
                        r_c = resource.get_resource(c_path, soft=True)
                        if r_c is not None:
                            options.append({'name': quote(c_path),
                                'value': r_c.get_title()})
                    if len(options) < 1:
                        return ''
                    elif len(options) == 1 and options[0]['name'] == '':
                        return ''
                    options.sort(key=itemgetter('value'))
                    name = 'folder%s' % (int(key[-1])+1)
                    level = int(key[-1]) + 1
                    widget = FolderWidget(name, value='', level=level,
                                          lower=(level+1),
                                          datatype=Enumerate(options=options))
                    return widget.render()
        return ''



class FolderWidget(SelectWidget):
    has_empty_option = True
    template = make_stl_template("""
        <select id="${id}" name="${name}"
          onchange="clean_subfolders(${lower});
            $('#f${lower}').load('/;get_folders?level${level}='+$(this).val())">
          <option value="" stl:if="has_empty_option"></option>
          <option stl:repeat="option options" value="${option/name}"
            selected="${option/selected}">${option/value}</option>
        </select>
        """)

    @proto_property
    def value(self):
        return quote(self._value)



class FoldersWidget(Widget):
    template = make_stl_template("""
      <script type="text/javascript">
          $(function(){
            $("#folder0").change(function(){
              $("#f1").load('/;get_folders?level0='+$(this).val());
            });
          });
      </script>
      <div id="f0">${folder0}</div>
      <div id="f1">${folder1}</div>
      <div id="f2">${folder2}</div>
      <div id="f3">${folder3}</div>
      <div id="f4">${folder4}</div>
    """)
    folder = None

    def folderX(self, x):
        """ folders -> folder courant
            folder  -> folder complet
            value   -> folder fils sélectionné
        """
        if self.folder is None:
            return None
        name = 'folder%s' % x
        folder_path = self.folder.abspath
        value = quote(str(folder_path[:x+1]))

        if len(folder_path) < x:
            return None
        base_folder = folder_path[:x]
        base_folder = get_context().database.get_resource(base_folder)

        # On affiche la liste si elle contient des items
        if list(base_folder.search_resources(format='folder')):
            return FolderWidget(name,
                datatype=FoldersEnumerate(base_folder=base_folder),
                value=value, lower=x+1, level=x).render()
        return None


    @proto_lazy_property
    def folder0(self):
        return self.folderX(0)

    @proto_lazy_property
    def folder1(self):
        return self.folderX(1)

    @proto_lazy_property
    def folder2(self):
        return self.folderX(2)

    @proto_lazy_property
    def folder3(self):
        return self.folderX(3)

    @proto_lazy_property
    def folder4(self):
        return self.folderX(4)



class DynamicEnumerate(Enumerate):
    """
    Automaticaly build an enumerate with all resources
    of a given class_id.
    results = [{'name': resource1.get_abspath()
                'title': resource1.get_title()}
               {'name': resource2.get_abspath()
                'title': resource2.get_title()}]
    """

    format = None

    @classmethod
    def get_options(cls):
        context = get_context()
        return [
            {'name': quote(str(res.abspath)), 'value': res.get_title()}
            for res in context.search(format=cls.format).get_resources() ]

    @classmethod
    def get_resource(cls, name):
        return get_context().database.get_resource(name)


    @classmethod
    def get_value(cls, name, default=None):
        if name is None:
            return
        resource = cls.get_resource(name)
        return resource.get_title()



class FoldersEnumerate(DynamicEnumerate):

    widget = FolderWidget

    @proto_lazy_property
    def base_folder(self):
        return get_context().root

    @proto_lazy_property
    def _value(self):
        return self.base_folder.abspath

    @proto_lazy_property
    def value(self):
        return quote(str(self._value))

    def get_options(self):
        base_folder = self.base_folder
        value = str(base_folder.get_resource(self._value).abspath)
        options = []
        for item in base_folder.search_resources(format='folder'):
            if item is not None:
                i_abspath = str(item.abspath)
                options.append({'name': quote(i_abspath),
                    'value': item.get_title(),
                    'selected': i_abspath in value})
        # Si 1 option, elle est sélectionnée
        if len(options) == 1:
            options[0]['selected'] = True
        options.sort(key=itemgetter('value'))
        return options



###########################################################################
# Common widgets to reuse
###########################################################################
title_widget = TextWidget('title', title=MSG(u'Title'))
description_widget = MultilineWidget('description',
                                     title=MSG(u'Description'), rows=8)
subject_widget = TextWidget('subject', title=MSG(u'Keywords'),
                            tip=MSG(u'Separated by comma'))
timestamp_widget = HiddenWidget('timestamp')
file_widget = FileWidget('file', title=MSG(u'Replace file'))
editarea_widget = EditAreaWidget('data', title=MSG(u'Body'))



# Registry with {datatype: widget, ...}
widgets_registry = {
        Boolean: RadioWidget,
        Date: DateWidget,
        DateTime: DatetimeWidget,
        Email: TextWidget,
        Enumerate: SelectWidget,
        Password_Datatype: PasswordWidget,
        PathDataType: PathSelectorWidget}

def get_default_widget(datatype):
    """Returns widget class from registry, TextWidget is default."""
    widget = widgets_registry.get(datatype, None)
    if widget is None:
        for d, w in widgets_registry.iteritems():
            if issubclass(datatype, d):
                return w
    return widget or TextWidget
