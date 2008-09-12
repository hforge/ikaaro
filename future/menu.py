# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Luis Arturo Belmar-Letelier <luis@itaapy.com>
# Copyright (C) 2007-2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2008 Nicolas Deram <nicolas@itaapy.com>
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
from itools import get_abspath
from itools.datatypes import is_datatype, Unicode
from itools.gettext import MSG
from itools.i18n import get_language_name
from itools.stl import stl
from itools.uri import Path

# Import from ikaaro
from ikaaro.file import File
from ikaaro.forms import BooleanRadio
from ikaaro.messages import MSG_CHANGES_SAVED
from ikaaro.registry import register_resource_class
from ikaaro.resource_ import DBResource
from ikaaro.resource_views import Breadcrumb
from ikaaro.skins import register_skin
from order import OrderAware

# Import from itools
from itools.datatypes import Boolean, String


###########################################################################
# Link
###########################################################################
class Link(File):

    class_id = 'link'
    class_version = '20071215'
    class_title = MSG(u'Link')
    class_description = MSG(u'Link')
    class_icon48 = 'future/images/Link48.png'
    class_icon16 = 'future/images/Link16.png'
    class_views = ['edit_metadata_form', 'state_form']


    @classmethod
    def get_metadata_schema(cls):
        schema = File.get_metadata_schema()
        schema['link'] = String
        schema['new_window'] = Boolean(default=False)
        return schema


    @staticmethod
    def new_instance_form(cls, context):
        # Use the default form
        return DBResource.new_instance_form(cls, context)

    @staticmethod
    def new_instance(cls, container, context):
        return DBResource.new_instance(cls, container, context)


    def GET(self, context):
        link = self.get_property('link')
        if link is not None:
            return context.uri.resolve2(link)
        return File.GET(self, context)


    add_link_form__access__ = 'is_allowed_to_edit'
    def addlink_form(self, context):
        # Build the bc
        if isinstance(self, File):
            start = self.parent
        else:
            start = self
        # Construct namespace
        namespace = {}
        namespace['bc'] = Breadcrumb(filter_type=File, start=start)
        namespace['message'] = context.get_form_value('message')

        prefix = self.get_abspath().get_pathto('/ui/future/link_addlink.xml')
        handler = self.get_resource('/ui/future/link_addlink.xml')
        return stl(handler, namespace, prefix=prefix)


    def edit_metadata_form(self, context):
        # Build the namespace
        namespace = {}
        # Language
        language = self.get_content_language(context)
        language_name = get_language_name(language)
        namespace['language_name'] = self.gettext(language_name)
        # Title
        namespace['title'] = self.get_property('title', language=language)
        # Description
        namespace['description'] = self.get_property('description',
                                                     language=language)
        namespace['link'] = self.get_property('link')
        new_window = self.get_property('new_window')
        labels = {'yes': u'New window', 'no': u'Current window'}
        widget =  BooleanRadio('new_window', labels=labels)
        namespace['target'] = widget.to_html(None, new_window)
        # Add a script
        context.scripts.append('/ui/future/link.js')

        handler = self.get_resource('/ui/future/link_edit_metadata.xml')
        return stl(handler, namespace)


    def edit_metadata(self, context):
        link = context.get_form_value('link').strip()
        if not link:
            return context.come_back(u'The link must be entered.')

        title = context.get_form_value('title', type=Unicode)
        description = context.get_form_value('description', type=Unicode)
        new_window = context.get_form_value('new_window', type=Boolean)
        # Set input data
        language = self.get_content_language(context)

        self.set_property('title', title, language=language)
        self.set_property('description', description, language=language)
        self.set_property('link', link)
        self.set_property('new_window', new_window)
        return context.come_back(MSG_CHANGES_SAVED)


    #######################################################################
    # API to be used by menu.py get_menu_namespace method
    #######################################################################
    def get_target_info(self):
        """Return a tuple with:
        example1 : '_blank', '../../;contact_form'
        example2 : '_top', '../../python'
        example3 : '_blank', 'http://www.google.com'
        """

        new_window = '_top'
        if self.get_property('new_window') is True:
            new_window = '_blank'

        return new_window, self.get_property('link')


    def has_target(self):
        return self.get_property('link') != None



###########################################################################
# Menu gestion
###########################################################################
def get_target_info(context, resource):
    """Return a tuple with:
    - a list made with the target path and if any the target resource
    - the target info '_top' or '_blank' or ...
    """
    if resource.has_target() is False:
        return None, None

    new_window, target = resource.get_target_info()
    if target and target.startswith('http://'):
        return [target], new_window

    target_rpath = Path(target)

    # Split relative target path and target method if any
    if target_rpath[-1].params:
        target_method = target_rpath.pop()
    else:
        target_method = None

    # get the real target resource
    site_root = context.resource.get_site_root()
    try:
        child = resource.get_resource(target_rpath)
    except LookupError:
        return None, None

    # make a url list with the target resource
    target_url = [ x.name for x in site_root.get_pathto(child) if x.name ]
    if target_method is not None:
        target_url.append(target_method)

    return target_url, new_window



def get_menu_namespace_level(context, url, menu_root, depth, show_first_child,
                             link_like=None):
    """Return a tabs list with the following structure:

    tabs = [{'active': False,
             'class': None,
             'id': u'tab_python',
             'label': u'Python',
             'path': '../python',
             'options': ...}, {...}]

    link_like can be class that implement get_target_info method
    """
    if is_datatype(menu_root, OrderAware) is False:
        return {}

    here, user = context.resource, context.user
    items = []
    tabs = {}

    for name in menu_root.get_ordered_names('ordered'):
        # Get the objects, check security
        resource = menu_root.get_resource(name)

        ac = resource.get_access_control()
        if ac.is_allowed_to_view(user, resource) is False:
            continue

        # Link special case for target and actual_url
        target = '_top'
        actual_url = here == resource
        is_link = (link_like and isinstance(resource, link_like))
        if is_link is True:
            target_url, new_window = get_target_info(context, resource)
            if target_url:
                actual_url = url == target_url

        # Subtabs
        subtabs = {}
        if depth > 1:
            subtabs = get_menu_namespace_level(context, url, resource, depth-1,
                                               show_first_child, link_like)

        # set active, in_path
        active, in_path = False, name in url
        if actual_url:
            active, in_path = True, False

        # set css class to 'active', 'in_path' or None
        css = (active and 'active') or (in_path and 'in_path') or None

        # set label and description
        label = resource.get_title()
        description = resource.get_property('description') or label

        # set path
        if is_link is True:
            # Do not active the link if it does not have target_url
            if target_url is None:
                path = None
            else:
                path = str(here.get_pathto(resource))
        else:
            path = str(here.get_pathto(resource))
            if show_first_child and depth > 1:
                if subtabs.get('items', None):
                    childs = subtabs['items']
                    first_child = childs[0]['path']
                    first_child = here.get_resource(first_child)
                    path = str(here.get_pathto(first_child))

        items.append({'id': 'tab_%s' % label.lower().replace(' ', '_'),
                      'path': path,
                      'name': name,
                      'label': here.gettext(label),
                      'description': here.gettext(description),
                      'active': active,
                      'class': css,
                      'target': target})

        # add options to the last dict in items
        items[-1]['options'] = subtabs
    tabs['items'] = items
    return tabs


def get_menu_namespace(context, depth=3, show_first_child=False, flat=True,
                       link_like=None):
    """Return dict with the following structure (for depth=3 lvl{0,1,2})

    {'flat': {'lvl0': [item_dic*],
              'lvl1': [item_dic*],
              'lvl2': [item_dic*]},
     'items': [item_dic*]}

    with

    item_dic =  [{'active': False,
                  'class': None,
                  'id': u'tab_python',
                  'label': u'Python',
                  'path': '../python',
                  'options': item_dic}]
    """

    request = context.request
    request_uri = str(request.request_uri)
    site_root = context.resource.get_site_root()
    method, path = context.view_name, context.uri.path
    url = [seg.name for seg in path if seg.name]
    if method:
        url += [';%s' % method]
    tabs = get_menu_namespace_level(context, url, site_root, depth,
                                    show_first_child, link_like)

    if flat:
        tabs['flat'] = {}
        items = tabs['flat']['lvl0'] = tabs.get('items', None)
        # initialize the levels
        for i in range(1, depth):
            tabs['flat']['lvl%s' % i] = None
        exist_items = True
        lvl = 1
        while (items is not None) and exist_items:
            exist_items = False
            for item in items:
                if item['class'] in ['active', 'in_path']:
                    if item['options']:
                        items = exist_items = item['options'].get('items')
                        if items:
                            tabs['flat']['lvl%s' % lvl] = items
                            lvl += 1
                        break
                    else:
                        items = None
                        break
    return tabs



#
# Register
#
register_resource_class(Link)
