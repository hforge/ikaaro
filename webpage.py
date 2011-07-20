# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2008 Henry Obein <henry@itaapy.com>
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

# Import from standard Library
from copy import deepcopy

# Import from itools
from itools.core import merge_dicts, is_thingy
from itools.datatypes import String
from itools.fs import FileName
from itools.gettext import MSG
from itools.html import xhtml_uri, XHTMLFile
from itools.stl import rewrite_uris
from itools.uri import Path, Reference, get_reference
from itools.web import BaseView, ERROR, get_context
from itools.xml import START_ELEMENT

# Import from ikaaro
from autoform import HTMLBody, rte_widget
from cc import Observable
from file_views import File_Edit
from text import Text
from registry import register_resource_class
from resource_ import DBResource


def _get_links(base, events):
    map = {'a': 'href', 'img': 'src', 'iframe': 'src',
           # Map
           'area': 'href',
           # Object
           # FIXME param tag can have both src and data attributes
           'object': 'data', 'param': 'src'}
    links = set()
    for event, value, line in events:
        if event != START_ELEMENT:
            continue
        tag_uri, tag_name, attributes = value
        if tag_uri != xhtml_uri:
            continue

        # Get the attribute name and value
        attr_name = map.get(tag_name)
        if attr_name is None:
            continue

        attr_name = (None, attr_name)
        value = attributes.get(attr_name)
        if value is None:
            continue

        reference = get_reference(value)

        # Skip empty links, external links and links to '/ui/'
        if reference.scheme or reference.authority:
            continue
        path = reference.path
        if not path or path.is_absolute() and path[0] == 'ui':
            continue

        # Strip the view
        name = path.get_name()
        if name and name[0] == ';':
            path = path[:-1]

        uri = base.resolve2(path)
        uri = str(uri)
        links.add(uri)
    return links


def _change_link(source, target, old_base, new_base, stream):
    map = {'a': 'href', 'img': 'src', 'iframe': 'src',
           # Map
           'area': 'href',
           # Object
           # FIXME param tag can have both src and data attributes
           'object': 'data', 'param': 'src'}

    for event in stream:
        # Process only elements of the XHTML namespace
        type, value, line = event
        if type != START_ELEMENT:
            yield event
            continue
        tag_uri, tag_name, attributes = value
        if tag_uri != xhtml_uri:
            yield event
            continue

        # Get the attribute name and value
        attr_name = map.get(tag_name)
        if attr_name is None:
            yield event
            continue

        attr_name = (None, attr_name)
        value = attributes.get(attr_name)
        if value is None:
            yield event
            continue

        reference = get_reference(value)

        # Skip empty links, external links and links to '/ui/'
        if reference.scheme or reference.authority:
            yield event
            continue
        path = reference.path
        if not path or path.is_absolute() and path[0] == 'ui':
            yield event
            continue

        # Strip the view
        name = path.get_name()
        if name and name[0] == ';':
            view = '/' + name
            path = path[:-1]
        else:
            view = ''

        # Check the link points to the resource that is moving
        path = old_base.resolve2(path)
        if path != source:
            yield event
            continue

        # Update the link
        # Build the new reference with the right path
        new_reference = deepcopy(reference)
        new_reference.path = str(new_base.get_pathto(target)) + view

        attributes[attr_name] = str(new_reference)
        yield START_ELEMENT, (tag_uri, tag_name, attributes), line


###########################################################################
# Views
###########################################################################
class WebPage_View(BaseView):
    access = 'is_allowed_to_view'
    title = MSG(u'View')
    icon = 'view.png'


    def GET(self, resource, context):
        return resource.get_html_data()



class WebPage_Edit(File_Edit):
    """WYSIWYG editor for HTML documents.
    """

    fields = ['title', 'state', 'data', 'description', 'subject']

    def _get_datatype(self, resource, context, name):
        if name == 'data':
            return HTMLBody(multilingual=True,
                            parameters_schema={'lang': String})

        return super(WebPage_Edit, self)._get_datatype(resource, context, name)


    def _get_widget(self, resource, context, name):
        if name == 'data':
            return rte_widget

        return super(WebPage_Edit, self)._get_widget(resource, context, name)


    def get_value(self, resource, context, name, datatype):
        if name == 'data':
            value = {}
            for language in resource.get_edit_languages(context):
                value[language] = resource.get_html_data(language=language)
            return value

        return File_Edit.get_value(self, resource, context, name, datatype)


    def action(self, resource, context, form):
        File_Edit.action(self, resource, context, form)
        if context.edit_conflict or is_thingy(context.message, ERROR):
            return

        # Send notifications
        resource.notify_subscribers(context)


    def set_value(self, resource, context, name, form):
        if name == 'data':
            changed = False
            for language, data in form['data'].iteritems():
                handler = resource.get_handler(language=language)
                if handler.set_body(data):
                    changed = True
            if changed:
                context.database.change_resource(resource)
            return False

        return File_Edit.set_value(self, resource, context, name, form)


###########################################################################
# Model
###########################################################################
class WebPage(Observable, Text):

    class_id = 'webpage'
    class_title = MSG(u'Web Page')
    class_description = MSG(u'Create and publish a Web Page.')
    class_icon16 = 'icons/16x16/html.png'
    class_icon48 = 'icons/48x48/html.png'
    class_views = ['view', 'edit', 'externaledit', 'subscribe', 'links',
                   'backlinks', 'commit_log']
    class_handler = XHTMLFile

    class_schema = merge_dicts(
        Text.class_schema,
        Observable.class_schema)



    def __init__(self, metadata):
        self.metadata = metadata
        self.handlers = {}


    def init_resource(self, body=None, filename=None, language=None, **kw):
        DBResource.init_resource(self, filename=filename, **kw)
        if body:
            handler = self.class_handler(string=body)
            extension = handler.class_extension
            name = FileName.encode((self.name, extension, language))
            self.parent.handler.set_handler(name, handler)


    def get_handler(self, language=None):
        # Content language
        if language is None:
            site_root = self.get_site_root()
            ws_languages = site_root.get_property('website_languages')
            handlers = [
                (x, self.get_handler(language=x)) for x in ws_languages ]
            languages = [ x for (x, y) in handlers if not y.is_empty() ]
            language = select_language(languages)
            # Default
            if language is None:
                language = ws_languages[0]
        # Hit
        if language in self.handlers:
            return self.handlers[language]
        # Miss
        cls = self.class_handler
        metadata = self.metadata
        database = metadata.database
        name = FileName.encode((self.name, cls.class_extension, language))
        key = database.fs.resolve(metadata.key, name)
        handler = database.get_handler(key, cls=cls, soft=True)
        if handler is None:
            handler = cls()
            database.push_phantom(key, handler)

        self.handlers[language] = handler
        return handler

    handler = property(get_handler, None, None, '')


    def get_handlers(self):
        languages = self.get_site_root().get_property('website_languages')
        return [ self.get_handler(language=x) for x in languages ]


    def rename_handlers(self, new_name):
        old_name = self.name
        extension = self.class_handler.class_extension
        langs = self.get_site_root().get_property('website_languages')

        return [ (FileName.encode((old_name, extension, x)),
                  FileName.encode((new_name, extension, x)))
                 for x in langs ]


    # FIXME These three methods are private, add the heading underscore
    def get_links(self):
        links = super(WebPage, self).get_links()
        base = self.get_abspath()
        languages = self.get_site_root().get_property('website_languages')
        for language in languages:
            handler = self.get_handler(language=language)
            links.update(_get_links(base, handler.events))
        return links


    def update_links(self,  source, target):
        super(WebPage, self).update_links(source, target)
        base = self.get_abspath()
        resources_new2old = get_context().database.resources_new2old
        base = str(base)
        old_base = resources_new2old.get(base, base)
        old_base = Path(old_base)
        new_base = Path(base)

        for handler in self.get_handlers():
            events = _change_link(source, target, old_base, new_base,
                                  handler.events)
            events = list(events)
            handler.set_changed()
            handler.events = events
        get_context().database.change_resource(self)


    def update_relative_links(self, source):
        super(WebPage, self).update_relative_links(source)
        target = self.get_abspath()
        resources_old2new = get_context().database.resources_old2new

        def my_func(value):
            # Skip empty links, external links and links to '/ui/'
            uri = get_reference(value)
            if uri.scheme or uri.authority or uri.path.is_absolute():
                return value
            path = uri.path
            if not path or path.is_absolute() and path[0] == 'ui':
                return value

            # Strip the view
            name = path.get_name()
            if name and name[0] == ';':
                view = '/' + name
                path = path[:-1]
            else:
                view = ''

            # Resolve Path
            # Calcul the old absolute path
            old_abs_path = source.resolve2(path)
            # Get the 'new' absolute parth
            new_abs_path = resources_old2new.get(old_abs_path, old_abs_path)

            path = str(target.get_pathto(new_abs_path)) + view
            value = Reference('', '', path, uri.query.copy(), uri.fragment)
            return str(value)

        for handler in self.get_handlers():
            if handler.database.is_phantom(handler):
                continue
            events = rewrite_uris(handler.events, my_func)
            events = list(events)
            handler.set_changed()
            handler.events = events


    #######################################################################
    # API
    #######################################################################
    def get_content_type(self):
        return 'application/xhtml+xml; charset=UTF-8'


    def get_html_data(self, language=None):
        document = self.get_handler(language=language)
        body = document.get_body()
        if body is None:
            return None
        return body.get_content_elements()


    def to_text(self, languages=None):
        if languages is None:
            languages = self.get_site_root().get_property('website_languages')
        result = {}
        for language in languages:
            handler = self.get_handler(language=language)
            result[language] = handler.to_text()
        return result



    #######################################################################
    # Views
    #######################################################################
    new_instance = DBResource.new_instance
    view = WebPage_View()
    edit = WebPage_Edit()



###########################################################################
# Register
###########################################################################
register_resource_class(WebPage, format='application/xhtml+xml')
