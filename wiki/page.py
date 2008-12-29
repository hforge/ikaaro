# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2007-2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2008 Gautier Hayoun <gautier.hayoun@itaapy.com>
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
from re import compile

# Import from docutils
from docutils import nodes
from docutils.core import publish_doctree
from docutils.readers import get_reader_class
from docutils.utils import SystemMessage

# Import from itools
from itools.gettext import MSG
from itools.handlers import checkid
from itools.uri import get_reference
from itools.web import get_context

# Import from ikaaro
from ikaaro.text import Text
from ikaaro.registry import register_resource_class
from ikaaro.resource_views import DBResource_NewInstance
from page_views import WikiPage_Edit, WikiPage_Help, WikiPage_ToPDF
from page_views import WikiPage_View



StandaloneReader = get_reader_class('standalone')


class WikiPage(Text):

    class_id = 'WikiPage'
    class_version = '20081114'
    class_title = MSG(u"Wiki Page")
    class_description = MSG(u"Wiki contents")
    class_icon16 = 'wiki/WikiPage16.png'
    class_icon48 = 'wiki/WikiPage48.png'
    class_views = ['view', 'to_pdf', 'edit', 'externaledit', 'upload',
                   'backlinks', 'edit_state', 'help']

    overrides = {
        # Security
        'file_insertion_enabled': 0,
        'raw_enabled': 0,
        # Encodings
        'input_encoding': 'utf-8',
        'output_encoding': 'utf-8',
    }


    #######################################################################
    # API
    #######################################################################
    def resolve_link(self, title):
        parent = self.parent

        # Try regular resource name or path
        try:
            return parent.get_resource(title)
        except (LookupError, UnicodeEncodeError):
            # Convert wiki name to resource name
            name = checkid(title)
            if name is None:
                return None
            try:
                return parent.get_resource(name)
            except LookupError:
                return None


    def get_document(self):
        parent = self.parent

        # Override dandling links handling
        class WikiReader(StandaloneReader):
            supported = ('wiki',)

            def wiki_reference_resolver(target):
                title = target['name']
                resource = self.resolve_link(title)
                if resource is None:
                    # Not Found
                    target['wiki_name'] = False
                else:
                    # Found
                    target['wiki_name'] = str(self.get_pathto(resource))

                return True

            wiki_reference_resolver.priority = 851
            unknown_reference_resolvers = [wiki_reference_resolver]

        # Publish!
        reader = WikiReader(parser_name='restructuredtext')
        document = publish_doctree(self.handler.to_str(), reader=reader,
                                   settings_overrides=self.overrides)

        context = get_context()
        # Assume internal paths are relative to the container
        for node in document.traverse(condition=nodes.reference):
            refuri = node.get('refuri')
            # Skip wiki or fragment link
            if node.get('wiki_name') or not refuri:
                continue
            reference = get_reference(refuri.encode('utf_8'))
            # Skip external
            if reference.scheme or reference.authority:
                continue
            # Note: absolute paths will be rewritten as relative paths
            try:
                resource = parent.get_resource(reference.path)
                node['refuri'] = context.get_link(resource)
            except LookupError:
                pass

        # Assume image paths are relative to the container
        for node in document.traverse(condition=nodes.image):
            uri  = node['uri'].encode('utf_8')
            reference = get_reference(uri)
            # Skip external
            if reference.scheme or reference.authority:
                continue
            # Strip the view
            path = reference.path
            if reference.path[-1] == ';download':
                path = path[:-1]
            # Get the resource
            try:
                resource = parent.get_resource(path)
            except LookupError:
                pass
            else:
                node['uri'] = '%s/;download' % context.get_link(resource)

        return document


    def get_links(self):
        base = self.get_abspath()

        links = []
        try:
            document = self.get_document()
        except SystemMessage:
            # The document is in a incoherent state
            return None
        for node in document.traverse(condition=nodes.reference):
            refname = node.get('wiki_name')
            if refname is False:
                # Wiki link not found
                title = node['name']
                path = checkid(title) or title
                path = base.resolve(path)
            elif refname:
                # Wiki link found, "refname" is the path
                path = base.resolve2(refname)
            else:
                # Regular link, include internal ones
                refuri = node.get('refuri')
                if refuri is None:
                    continue
                reference = get_reference(refuri.encode('utf_8'))
                # Skip external
                if reference.scheme or reference.authority:
                    continue
                path = base.resolve2(reference.path)
            path = str(path)
            links.append(path)

        for node in document.traverse(condition=nodes.image):
            uri = node['uri'].encode('utf_8')
            reference = get_reference(uri)
            # Skip external image
            if reference.scheme or reference.authority:
                continue
            # Strip the view
            path = reference.path
            if path[-1] == ';download':
                path = path[:-1]
            # Resolve the path
            path = base.resolve(path)
            path = str(path)
            links.append(path)

        return links


    def change_link(self, old_path, new_path,
                    links_re = compile(r'(\.\. .*?: )(\S*)')):
        old_data = self.handler.to_str()
        new_data = []

        not_uri = 0
        base = self.parent.get_abspath()
        for segment in links_re.split(old_data):
            not_uri = (not_uri + 1) % 3
            if not not_uri:
                reference = get_reference(segment)

                # Skip external link
                if reference.scheme or reference.authority:
                    new_data.append(segment)
                    continue

                # Strip the view
                path = reference.path
                if path[-1] == ';download':
                    path = path[:-1]
                    view = '/;download'
                else:
                    view = ''

                # Resolve the path
                path = base.resolve(path)

                # Match ?
                if path == old_path:
                    segment = str(base.get_pathto(new_path)) + view
            new_data.append(segment)
        new_data = ''.join(new_data)
        self.handler.load_state_from_string(new_data)
        get_context().server.change_resource(self)


    #######################################################################
    # Update service
    #######################################################################
    def update_20081114(self,
            links_migration_re = compile(r'\.\. figure:: ([^;]*?)(?!;)(\s)'),
            links_migration_sub = r'.. figure:: \1/;download\2'):
        data = self.handler.to_str()
        data = links_migration_re.sub(links_migration_sub, data)
        self.handler.load_state_from_string(data)


    #######################################################################
    # User Interface
    #######################################################################
    new_instance = DBResource_NewInstance()
    view = WikiPage_View()
    to_pdf = WikiPage_ToPDF()
    edit = WikiPage_Edit()
    help = WikiPage_Help()


    def get_context_menus(self):
        return self.parent.get_context_menus()



###########################################################################
# Register
###########################################################################
register_resource_class(WikiPage)
