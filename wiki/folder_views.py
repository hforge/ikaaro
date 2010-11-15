# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
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
from cStringIO import StringIO

# Import from itools
from itools.core import merge_dicts
from itools.datatypes import Unicode, LanguageTag
from itools.fs import FileName
from itools.fs.common import get_mimetype
from itools.gettext import MSG
from itools.handlers import checkid
from itools.i18n import get_language_name
from itools.web import ERROR

# Import from ikaaro
from ikaaro.datatypes import FileDataType
from ikaaro.messages import MSG_BAD_NAME, MSG_NAME_CLASH
from ikaaro.registry import get_resource_class
from ikaaro.resource_views import DBResource_AddBase
from ikaaro.utils import generate_name
from ikaaro.views import ContextMenu
from page import WikiPage
from page_views import ALLOWED_FORMATS


class WikiMenu(ContextMenu):
    title = MSG(u'Wiki')

    def get_items(self, resource, context):
        # If called from a child
        if isinstance(resource, WikiPage):
            resource = resource.parent
        # Namespace
        base = context.get_link(resource)
        return [
            {'title': resource.get_view(view).title,
             'href': '%s/;%s' % (base, view)}
            for view in resource.class_views ]



class DBResource_ImportODT(DBResource_AddBase):

    template = '/ui/wiki/importodt.xml'
    element_to_add = 'odt'

    schema = merge_dicts(DBResource_AddBase.schema,
                         title=Unicode(),
                         subject=Unicode(),
                         keywords=Unicode(),
                         comments=Unicode(),
                         language=LanguageTag(default=('en', 'EN')))

    action_upload_schema = merge_dicts(schema,
                                       file=FileDataType(mandatory=True))


    def get_item_classes(self):
        from ikaaro.file import ODT
        return self.item_classes if self.item_classes else (ODT,)


    def get_configuration(self):
        return {
            'show_browse': False,
            'show_external': False,
            'show_insert': False,
            'show_upload': True}


    def get_namespace(self, resource, context):
        ns = DBResource_AddBase.get_namespace(self, resource, context)
        root = resource.get_site_root()
        languages = root.get_property('website_languages')

        ns['meta-lang'] = []
        for code in languages:
            ns['meta-lang'].append({'name': get_language_name(code),
                                    'value': code})
        return ns


    def add_wiki_page(self, resource, name, title, content):
        """Add a WikiPage in resource, with title and content set.
        """
        WikiPage.make_resource(WikiPage, resource, name,
                title={'en': title}, body=content)


    def convert_images(self, content, document, resource):
        result = []
        template = '.. image:: Pictures/'
        for line in content.splitlines():
            if line.startswith(template):

                filename = line[len(template):]
                data = document.get_part('Pictures/%s' % filename)
                name, a_type, language = FileName.decode(filename)

                # Check the filename is good
                name = checkid(name)
                if name is None:
                    continue

                # Check the name is free
                if resource.get_resource(name, soft=True) is not None:
                    continue

                # Get mimetype / class
                mimetype = get_mimetype(filename)
                cls = get_resource_class(mimetype)

                # Add the image
                cls.make_resource(cls, resource, name, data, format=mimetype,
                                  filename=filename, extension=a_type)

                # And modify the page
                result.append('.. figure:: %s' % name)
                result.append('   :width: 350px')

            else:
                result.append(line)

        return '\r\n'.join(result)


    def format_meta(self, form, template_name, toc_depth, language):
        """Format the metadata of a rst book from a lpod document.
        """
        content = []
        content.append(u'   :template: %s' % template_name)
        content.append(u'   :toc-depth: %s' % toc_depth)
        for key in ['title', 'subject', 'comments', 'keywords']:
            content.append(u'   :%s: %s' % (key,  form[key]))
        content.append(u'   :language: %s' % language)
        content.append(u'')
        return u"\n".join(content).encode('utf_8')


    def get_cover_name(self, resource, document, template_name):

        # Compute an explicit name
        name = document.get_meta().get_title()
        if not name:
            name = template_name
        if name:
            name = 'cover_%s' % checkid(name)
        else:
            name = 'cover'
        return generate_name(name, resource.get_names())


    def insert_notes_and_annotations(self, lpod_context, content):

        # Insert the notes
        footnotes = lpod_context['footnotes']
        if footnotes:
            content.append(u'\n')
            for citation, body in footnotes:
                content.append(u'.. [#] %s\n' % body)
            # Append a \n after the notes
            content.append(u'\n')
            # Reset
            lpod_context['footnotes'] = []

        # Insert the annotations
        annotations = lpod_context['annotations']
        if annotations:
            content.append(u'\n')
            for annotation in annotations:
                content.append('.. [#] %s\n' % annotation)
            # Reset
            lpod_context['annotations'] = []


    def insert_endnotes(self, lpod_context, content):

        # Insert the end notes
        endnotes = lpod_context['endnotes']
        if endnotes:
            content.append(u'\n\n')
            for citation, body in endnotes:
                content.append(u'.. [*] %s\n' % body)
            # Reset
            lpod_context['endnotes'] = []


    def format_content(self, resource, data, template_name):
        """Format the content of a rst book from a lpod document body.
        """

        # Get the body
        from lpod.document import odf_get_document
        document = odf_get_document(StringIO(data))
        body = document.get_body()

        # Create a context for the lpod functions
        lpod_context = {'document': document,
                        'footnotes': [],
                        'endnotes': [],
                        'annotations': [],
                        'rst_mode': True}

        # Main loop
        name = None
        title = 'Cover'
        links = u''
        max_level = 0
        last_level = 1
        content = []
        for element in body.get_children():

            # The headings are used to split the document
            if element.get_tag() == 'text:h':

                # 1- Save this page

                # Generate the content
                self.insert_endnotes(lpod_context, content)
                content =  u''.join(content).encode('utf-8')
                content = self.convert_images(content, document, resource)

                # In the cover ?
                if name is None:
                    name = cover = self.get_cover_name(resource, document,
                                                       template_name)

                # Add the page
                self.add_wiki_page(resource, name, title, content)

                # 2- Prepare the next page

                # Compute level and update max_level
                level = element.get_outline_level()
                max_level = max(level, max_level)

                # Get the title
                fake_context = dict(lpod_context)
                fake_context['rst_mode'] = False
                title = element.get_formatted_text(fake_context)

                # Start a new content with the title, but without the first
                # '\n'
                content = [element.get_formatted_text(lpod_context)[1:]]

                # Search for a free WikiPage name
                name = checkid(title) or 'invalid-name'
                names = resource.get_names()
                name = generate_name(name, names)

                # Update links (add eventually blank levels to avoid a problem
                # with an inconsistency use of levels in the ODT file)
                for x in range(last_level + 1, level):
                    links += u'   ' * x + u'-\n'
                last_level = level
                links += u'   ' * level + u'- `' + name + u'`_\n'

            # The tables
            elif element.get_tag() == 'table:table':
                content.append(element.get_formatted_text(lpod_context))

            # An other element
            else:
                content.append(element.get_formatted_text(lpod_context))
                self.insert_notes_and_annotations(lpod_context, content)


        # 3- Save the last page

        # Generate the content
        self.insert_endnotes(lpod_context, content)
        content =  u''.join(content).encode('utf-8')
        content = self.convert_images(content, document, resource)

        # In the cover ?
        if name is None:
            name = cover = self.get_cover_name(resource, document,
                                               template_name)

        # Add the page
        self.add_wiki_page(resource, name, title, content)

        return cover, links, max_level


    def get_language(self, language):
        """Format appropriate language code.
        """
        # Special case for languages
        if language:
            language, locality = language
            if locality:
                return '%s-%s' % (language, locality)
            else:
                return language
        else:
            return self.get_site_root().get_default_language()


    def do_import(self, resource, data, form, template_name):
        """Format the content of a rst book and create related resources.
        """

        cover, links, toc_depth = self.format_content(resource, data,
                                                      template_name)
        language = self.get_language(form['language'])
        meta = self.format_meta(form, template_name, toc_depth, language)
        book = u' `%s`_\n%s\n%s' % (cover, meta, links)

        # Escape \n for javascript
        book = book.replace(u'\n', u'\\n').encode('utf-8')

        return book


    def save_template(self, context, file, target_path):
        """Save the imported template.
        """
        filename, mimetype, body = file
        name, type, language = FileName.decode(filename)
        # Check the filename is good
        name = checkid(name)
        if name is None:
            context.message = MSG_BAD_NAME
            return

        # Get the container
        container = context.root.get_resource(target_path)

        # Check the name is free
        if container.get_resource(name, soft=True) is not None:
            context.message = MSG_NAME_CLASH
            return

        # Add the image to the resource
        cls = get_resource_class(mimetype)
        cls.make_resource(cls, container, name, body, format=mimetype,
                          filename=filename, extension=type)
        return name


    def action_upload(self, resource, context, form):
        """Insert a wikibook directly. The uploaded document is saved.
        """
        # Check the mimetype
        a_file = form['file']
        filename, mimetype, data = a_file
        if mimetype not in ALLOWED_FORMATS:
            context.message = ERROR(u'"%s" is not an OpenDocument Text' %
                    filename)
            return

        # Save the file
        target_path = form['target_path']
        template_name = self.save_template(context, a_file, target_path)
        if template_name is None:
            return

        # Return javascript
        scripts = self.get_scripts(context)
        context.add_script(*scripts)

        # Build RST Book
        wiki_book = self.do_import(resource, data, form, template_name)
        return self.get_javascript_return(context, wiki_book)
