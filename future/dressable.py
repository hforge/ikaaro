# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2007-2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2008 Nicolas Deram <nicolas@itaapy.com>
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
from operator import itemgetter
from warnings import warn

# Import from itools
from itools.gettext import MSG
from itools.html import xhtml_uri
from itools.stl import set_prefix
from itools.uri import get_reference
from itools.xml import XMLParser, START_ELEMENT

# Import from ikaaro
from ikaaro.file import Image
from ikaaro.folder import Folder
from ikaaro.html import ResourceWithHTML, WebPage
from ikaaro.registry import register_resource_class
from ikaaro.views import CompositeForm, ContextMenu
from ikaaro.wiki import WikiPage
from ikaaro.workflow import WorkflowAware


class Dressable_Menu(ContextMenu):

    title = MSG(u'Edit')

    def get_items(self, resource, context):
        items = []
        base_path = ''
        if not isinstance(resource, Dressable):
            resource = resource.parent
            base_path = '../'
            if not isinstance(resource, Dressable):
                return []

        for name, value in resource.layout.iteritems():
            if not isinstance(value, tuple):
                msg = u'Layout items MUST be 2 values tuples: '
                msg += u'"%s" is incorrect' % name
                warn(msg)
                continue
            name, cls = value
            if resource.has_resource(name):
                # Add edit link
                items.append(
                    {'name': name,
                     'title': MSG(u'%s %s' % (cls.class_title.gettext(), name)),
                     'href': '%s%s/;edit' % (base_path, name),
                     'class': 'nav_active'})
            else:
                # Add new_resource link
                items.append(
                    {'name': name,
                     'title': MSG(u'Add new %s' % cls.class_title.gettext()),
                     'href': ('%s;new_resource?type=%s&title=%s' %
                              (base_path, cls.class_id, name)),
                     'class': 'nav_active'})
        items.sort(key=itemgetter('name'))
        # Dressable metadata
        items.insert(0,
            {'title': MSG(u'Metadata'),
             'href': '%s;edit' % base_path,
             'class': 'nav_active'})
        # Back to preview
        items.append(
            {'title': MSG(u'Preview'),
             'href': '%s.' % base_path,
             'class': 'nav_active'})
        return items



class Dressable_View(CompositeForm):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    icon = 'view.png'
    template = '/ui/future/dressable_view.xml'


    def GET(self, resource, context):
        stream = CompositeForm.GET(self, resource, context)
        prefix = '%s/' % resource.name
        return set_prefix(stream, prefix)


    def get_view(self, resource, context, item):
        if isinstance(item, WebPage):
            return item.view.GET
        if isinstance(item, Image):
            return resource._get_image
        # TODO We should implement a specific view to display wiki page as HTML
        if isinstance(item, WikiPage):
            return item.view.GET
        return getattr(self, item, None)


    def get_namespace(self, resource, context):
        items = []
        for name, value in resource.layout.iteritems():
            content = ''
            if isinstance(value, tuple):
                name, kk = value
                if resource.has_resource(name):
                    item = resource.get_resource(name)
                    # get view to show current item
                    method = self.get_view(resource, context, item)
                    value = method(item, context)
                else:
                    value = None
            else:
                # get view to display
                value = getattr(resource, 'data')(context)
            items.append({'id': name, 'content': value})
        return {'items': items}



class Dressable(Folder, ResourceWithHTML):
    """A Dressable resource is a folder with a specific view which is defined
    by the layout. In addition of the layout, it is necessary to redefine
    the variable __fixed_handlers__.
    """

    class_id = 'dressable'
    class_version = '20081118'
    class_title = MSG(u'Dressable')
    class_description = MSG(u'A dressable folder')
    class_views = ['view', 'browse_content', 'preview_content']
    __fixed_handlers__ = ['index']
    layout = {'content': ('index', WebPage),
              'image1': ('image1', Image)}
    context_menus = [Dressable_Menu()]


    @staticmethod
    def _make_resource(cls, folder, name, **kw):
        Folder._make_resource(cls, folder, name, **kw)
        # populate the dressable
        cls._populate(cls, folder, name)


    @staticmethod
    def _populate(cls, folder, base_name):
        """Populate the dressable from the layout"""
        for key, data in cls.layout.iteritems():
            if isinstance(data, tuple):
                handler_name, handler_cls = data
                if issubclass(handler_cls, WebPage):
                    full_name = '%s/%s.metadata' % (base_name, handler_name)
                    metadata = handler_cls.build_metadata()
                    if issubclass(handler_cls, WorkflowAware):
                        metadata.set_property('state', 'public')
                    folder.set_handler(full_name, metadata)


    def get_document_types(self):
        return [self.__class__] + Folder.get_document_types(self)


    def get_html_document(self, language=None):
        resource = self.get_resource('index')
        return resource.get_html_document(language)


    def _get_image(self, item, context):
        return XMLParser('<img src="%s/;download"/>' % context.get_link(item))


    #######################################################################
    # User interface
    #######################################################################
    view = Dressable_View()


    #######################################################################
    # Update
    #######################################################################
    def update_20081118(self):
        def fix_links(stream):
            for event in stream:
                type, value, line = event
                if type != START_ELEMENT:
                    yield event
                    continue
                tag_uri, tag_name, attributes = value
                if tag_uri != xhtml_uri:
                    yield event
                    continue
                if tag_name not in ('img', 'a'):
                    yield event
                    continue
                if tag_name == 'img':
                    attr_name = 'src'
                else:
                    attr_name = 'href'
                value = attributes.get((None, attr_name))
                if value is None:
                    yield event
                    continue
                uri = get_reference(value)
                if uri.scheme or uri.authority or not uri.path:
                    yield event
                    continue
                if value.startswith('/ui/'):
                    yield event
                    continue
                # Fix link
                uri = '../' + str(uri)
                attributes = attributes.copy()
                attributes[(None, attr_name)] = str(uri)
                yield START_ELEMENT, (tag_uri, tag_name, attributes), line

        languages = self.get_site_root().get_property('website_languages')
        for wp in self.search_resources(cls=WebPage):
            for language in languages:
                handler = wp.get_handler(language=language)
                events = list(fix_links(handler.events))
                handler.set_changed()
                handler.events = events


register_resource_class(Dressable)
