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
from itools.gettext import MSG
from itools.handlers import checkid
from itools.i18n import get_language_name
from itools.web import ERROR

# Import from ikaaro
from ikaaro.datatypes import FileDataType
from ikaaro.messages import MSG_BAD_NAME, MSG_NAME_CLASH
from ikaaro.registry import get_resource_class
from ikaaro.resource_views import DBResource_AddBase
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


    def format_paragraph(self, paragraph, lpod_context):
        """Format a paragraph with blank lines.
        """
        paragraph = paragraph.get_formatted_text(lpod_context)
        return [u'', paragraph, u'']


    def format_list(self, lpod_list, lpod_context):
        """Format a list with indentation from an odf_list object.
        """
        lines = lpod_list.get_formatted_text(lpod_context).splitlines()
        result = [u'']
        for line in lines[1:-1]:
           result.extend([u'   ', line, u''])
        return result


    def format_content(self, resource, body, lpod_context):
        """Format the content of a rst book from a lpod document body.
        """
        from lpod.list import odf_list
        from lpod.paragraph import odf_paragraph
        links = u''
        heading_list = body.get_heading_list()
        max_level = 0
        for heading in heading_list:
            level = heading.get_outline_level()
            max_level = max(level, max_level)
            lines = heading.get_formatted_text(lpod_context).splitlines()
            # Search for a free WikiPage name
            name = checkid(lines[1]) or 'invalid-name'

            # Build the link
            line = u'   ' * level + u'- `' + name + u'`_\n'
            links = links + line

            # Build the wiki page content from the odf
            content = []
            paragraph = heading.get_next_sibling()
            # Write the note
            while type(paragraph) in [odf_paragraph, odf_list]:
                if type(paragraph) is odf_list:
                    content += self.format_list(paragraph, lpod_context)
                else:
                    content += self.format_paragraph(paragraph, lpod_context)
                paragraph = paragraph.get_next_sibling()
            if content:
                content = ['.. note::', ''] + content + ['']
            # Write the title
            content = lines[1:] + content
            # Create the page
            content = u'\n'.join(content).encode('utf-8')
            self.add_wiki_page(resource, name, lines[1], content)

        return links, max_level


    def format_meta(self, document, form, template_name, toc_depth, language):
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


    def format_cover(self, resource, body, lpod_context):
        """Format the cover and return his name.
        """
        self.add_wiki_page(resource, 'cover', u'Cover', '')
        return 'cover'


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


    def do_import(self, resource, uri, form, template_name):
        """Format the content of a rst book and create related resources.
        """
        from lpod.document import odf_get_document
        toc_depth = 0
        document = odf_get_document(uri)
        body = document.get_body()
        lpod_context = {'document': document,
                        'footnotes': [],
                        'endnotes': [],
                        'annotations': [],
                        'rst_mode': True}

        language = self.get_language(form['language'])
        links, toc_depth = self.format_content(resource, body, lpod_context)
        meta = self.format_meta(document, form, template_name, toc_depth,
                language)
        cover = self.format_cover(resource, body, lpod_context)
        book = u' `%s`_\n%s\n%s' % (cover, meta, links)

        # Escape \n for javascript
        book = book.replace(u'\n', u'\\n').encode('utf-8')

        return book


    def save_template(self, context, file, target_path):
        """Save the imported template.
        """
        filename, mimetype, body = file
        decode = FileName.decode(filename)
        name, type, language = decode
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
        file = form['file']
        filename, mimetype, body = file
        if mimetype not in ALLOWED_FORMATS:
            context.message = ERROR(u'"%s" is not an OpenDocument Text' %
                    filename)
            return
        # Save the file
        target_path = form['target_path']
        template_name = self.save_template(context, file, target_path)
        if template_name is None:
            return
        # Return javascript
        scripts = self.get_scripts(context)
        context.add_script(*scripts)

        # Build RST Book
        buffer = StringIO(body)
        wiki_book = self.do_import(resource, buffer, form, template_name)
        return self.get_javascript_return(context, wiki_book)
