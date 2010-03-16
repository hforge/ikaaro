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
from urllib import urlencode

# Import from docutils
from docutils import nodes
from docutils.core import publish_doctree
from docutils.languages.en import labels
from docutils.readers import get_reader_class
from docutils.parsers.rst import directives, Directive
from docutils.parsers.rst.directives import register_directive
from docutils.utils import SystemMessage

# Import from itools
from itools.gettext import MSG
from itools.handlers import checkid
from itools.uri import get_reference
from itools.web import get_context

# Import from ikaaro
from ikaaro.text import Text
from ikaaro.resource_ import DBResource
from page_views import WikiPage_Edit, WikiPage_Help, WikiPage_ToPDF
from page_views import WikiPage_View, WikiPage_ToODT
from page_views import is_external, BacklinksMenu



StandaloneReader = get_reader_class('standalone')



# Class name gives the DOM element name
class book(nodes.Admonition, nodes.Element):
    pass



class Book(Directive):
    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True
    option_spec = {'cover': directives.uri,
                   'toc-depth': directives.positive_int}
    has_content = True


    def run(self):
        self.assert_has_content()
        # Cover page
        if self.arguments:
            # Push cover as an option
            cover_uri = checkid(self.arguments[0][1:-2])
            self.options['cover'] = directives.uri(cover_uri)
        book_node = book(self.block_text, **self.options)
        if self.arguments:
            # Display the cover
            cover_text = self.arguments.pop(0)
            textnodes, messages = self.state.inline_text(cover_text,
                    self.lineno)
            book_node += nodes.title(cover_text, '', *textnodes)
            book_node += messages
        # Parse inner list
        self.state.nested_parse(self.content, self.content_offset, book_node)
        # Automatically number pages
        for bullet_list in book_node.traverse(condition=nodes.bullet_list):
            bullet_list.__class__ = nodes.enumerated_list
            bullet_list.tagname = 'enumerated_list'
        return [book_node]



class WikiPage(Text):
    class_id = 'WikiPage'
    class_title = MSG(u"Wiki Page")
    class_description = MSG(u"Wiki contents")
    class_icon16 = 'wiki/WikiPage16.png'
    class_icon48 = 'wiki/WikiPage48.png'
    class_views = ['view', 'to_pdf', 'to_odt', 'edit', 'externaledit',
            'edit_state', 'backlinks', 'commit_log', 'help']

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


    def set_new_resource_link(self, node):
        node['classes'].append('nowiki')
        prefix = self.get_pathto(self.parent)
        title = node['name']
        title_encoded = title.encode('utf_8')
        params = {'type': self.__class__.__name__,
                  'title': title_encoded,
                  'name': checkid(title) or title_encoded}
        refuri = "%s/;new_resource?%s" % (prefix,
                                          urlencode(params))
        node['refuri'] = refuri


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
            resource = self.get_resource(reference.path, soft=True)
            if resource is None:
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
        base = self.get_abspath()

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
        get_context().database.change_resource(self)


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
    new_instance = DBResource.new_instance
    view = WikiPage_View()
    to_pdf = WikiPage_ToPDF()
    edit = WikiPage_Edit()
    to_odt = WikiPage_ToODT()
    help = WikiPage_Help()


    def get_context_menus(self):
        return [BacklinksMenu()] + self.parent.get_context_menus()



# Register dummy book directive for ODT export
nodes._add_node_class_names(['book'])
nodes.book = book
register_directive('book', Book)
labels['book'] = ''
