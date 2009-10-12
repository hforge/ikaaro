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
from itools.http import get_context
from itools.uri import get_reference

# Import from ikaaro
from ikaaro.text import Text
from ikaaro.registry import register_document_type
from page_views import WikiPage_NewInstance, WikiPage_Edit, WikiPage_Help
from page_views import WikiPage_ToPDF, WikiPage_View
from page_views import is_external



StandaloneReader = get_reader_class('standalone')


class WikiPage(Text):

    class_id = 'WikiPage'
    class_title = MSG(u"Wiki Page")
    class_description = MSG(u"Wiki contents")
    class_icon16 = 'wiki/WikiPage16.png'
    class_icon48 = 'wiki/WikiPage48.png'
    class_views = ['view', 'to_pdf', 'edit', 'externaledit', 'edit_state',
                   'backlinks', 'commit_log', 'help']

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
            name = str(title)
        except UnicodeEncodeError:
            pass
        else:
            resource = parent.get_resource(name, soft=True)
            if resource is not None:
                return resource

        # Convert wiki name to resource name
        name = checkid(title)
        if name is None:
            return None
        return parent.get_resource(name, soft=True)


    def get_doctree(self):
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
                    target['wiki_name'] = str(resource.get_canonical_path())

                return True

            wiki_reference_resolver.priority = 851
            unknown_reference_resolvers = [wiki_reference_resolver]

        # Publish!
        reader = WikiReader(parser_name='restructuredtext')
        doctree = publish_doctree(self.handler.to_str(), reader=reader,
                settings_overrides=self.overrides)

        # Assume internal paths are relative to the container
        for node in doctree.traverse(condition=nodes.reference):
            refuri = node.get('refuri')
            # Skip wiki or fragment link
            if node.get('wiki_name') or not refuri:
                continue
            reference = get_reference(refuri.encode('utf_8'))
            # Skip external
            if is_external(reference):
                continue
            # Resolve absolute path
            resource = parent.get_resource(reference.path, soft=True)
            if resource is None:
                continue
            refuri = str(resource.get_canonical_path())
            # Restore fragment
            if reference.fragment:
                refuri = "%s#%s" % (refuri, reference.fragment)
            node['refuri'] = refuri

        # Assume image paths are relative to the container
        for node in doctree.traverse(condition=nodes.image):
            reference = get_reference(node['uri'].encode('utf_8'))
            # Skip external
            if is_external(reference):
                continue
            # Strip the view
            path = reference.path
            if path[-1][0] == ';':
                path = path[:-1]
            # Resolve absolute path
            resource = parent.get_resource(path, soft=True)
            if resource is not None:
                node['uri'] = str(resource.get_canonical_path())

        return doctree


    def get_links(self):
        base = self.get_physical_path()

        links = []
        try:
            doctree = self.get_doctree()
        except SystemMessage:
            # The doctree is in a incoherent state
            return None
        for node in doctree.traverse(condition=nodes.reference):
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
                if is_external(reference):
                    continue
                path = base.resolve2(reference.path)
            path = str(path)
            links.append(path)

        for node in doctree.traverse(condition=nodes.image):
            reference = get_reference(node['uri'].encode('utf_8'))
            # Skip external image
            if is_external(reference):
                continue
            # Resolve the path
            path = base.resolve(reference.path)
            path = str(path)
            links.append(path)

        return links


    def update_links(self, source, target,
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
                if is_external(reference):
                    new_data.append(segment)
                    continue

                # Strip the view
                path = reference.path
                if path and path[-1] == ';download':
                    path = path[:-1]
                    view = '/;download'
                else:
                    view = ''

                # Resolve the path
                path = base.resolve(path)

                # Match ?
                if path == source:
                    segment = str(base.get_pathto(target)) + view
            new_data.append(segment)
        new_data = ''.join(new_data)
        self.handler.load_state_from_string(new_data)
        get_context().change_resource(self)


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
    new_instance = WikiPage_NewInstance()
    view = WikiPage_View()
    to_pdf = WikiPage_ToPDF()
    edit = WikiPage_Edit()
    help = WikiPage_Help()


    def get_context_menus(self):
        return self.parent.get_context_menus()



###########################################################################
# Register
###########################################################################
register_document_type(WikiPage)
