# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
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
from re import subn
from tempfile import mkdtemp
from subprocess import call
from urllib import urlencode
from mimetypes import guess_extension

# Import from docutils
from docutils.core import (Publisher, publish_doctree, publish_from_doctree,
    publish_string)
from docutils.io import StringOutput, DocTreeInput
from docutils.readers import get_reader_class
from docutils.readers.doctree import Reader
from docutils.utils import SystemMessage
from docutils import nodes

# Import from itools
from itools import vfs
from itools.datatypes import DateTime, FileName, XML
from itools.handlers import checkid, get_handler, File as FileHandler
from itools.stl import stl
from itools.xml import XMLParser, XMLError
from itools.uri import get_reference
from itools.uri.mailto import Mailto

# Import from ikaaro
from ikaaro.base import DBObject
from ikaaro.messages import MSG_EDIT_CONFLICT, MSG_CHANGES_SAVED
from ikaaro.text import Text
from ikaaro.registry import register_object_class



StandaloneReader = get_reader_class('standalone')



class WikiPage(Text):

    class_id = 'WikiPage'
    class_version = '20071217'
    class_title = u"Wiki Page"
    class_description = u"Wiki contents"
    class_icon16 = 'wiki/WikiPage16.png'
    class_icon48 = 'wiki/WikiPage48.png'
    class_views = [['view', 'to_pdf'],
                   ['edit_form', 'externaledit', 'upload_form'],
                   ['backlinks'],
                   ['edit_metadata_form'],
                   ['state_form'],
                   ['help']]

    overrides = {
        # Security
        'file_insertion_enabled': 0,
        'raw_enabled': 0,
        # Encodings
        'input_encoding': 'utf-8',
        'output_encoding': 'utf-8',
    }


    @staticmethod
    def new_instance_form(cls, context):
        return DBObject.new_instance_form(cls, context)


    @staticmethod
    def new_instance(cls, container, context):
        return DBObject.new_instance(cls, container, context)


    GET__mtime__ = None
    GET__access__ = True
    def GET(self, context):
        return context.uri.resolve2(';view')


    #######################################################################
    # API
    #######################################################################
    def resolve_link(self, title):
        parent = self.parent

        # Try regular object name or path
        try:
            return parent.get_object(title)
        except (LookupError, UnicodeEncodeError):
            # Convert wiki name to object name
            name = checkid(title)
            if name is None:
                return None
            try:
                return parent.get_object(name)
            except LookupError:
                return None


    def get_document(self):
        parent = self.parent

        # Override dandling links handling
        class WikiReader(StandaloneReader):
            supported = ('wiki',)

            def wiki_reference_resolver(target):
                title = target['name']
                object = self.resolve_link(title)
                if object is None:
                    # Not Found
                    target['wiki_name'] = False
                else:
                    # Found
                    target['wiki_name'] = str(self.get_pathto(object))

                return True

            wiki_reference_resolver.priority = 851
            unknown_reference_resolvers = [wiki_reference_resolver]

        # Publish!
        reader = WikiReader(parser_name='restructuredtext')
        document = publish_doctree(self.handler.to_str(), reader=reader,
                                   settings_overrides=self.overrides)

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
                object = parent.get_object(reference.path)
                node['refuri'] = str(self.get_pathto(object))
            except LookupError:
                pass

        # Assume image paths are relative to the container
        for node in document.traverse(condition=nodes.image):
            uri  = node['uri'].encode('utf_8')
            reference = get_reference(uri)
            # Skip external
            if reference.scheme or reference.authority:
                continue
            try:
                object = parent.get_object(reference.path)
                node['uri'] = str(self.get_pathto(object))
            except LookupError:
                pass

        return document


    def get_links(self):
        base = self.get_abspath()

        links = []
        document = self.get_document()
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
            path = base.resolve2(reference.path)
            path = str(path)
            links.append(path)

        return links


    #######################################################################
    # UI / View
    #######################################################################
    view__sublabel__ = u'HTML'
    view__icon__ = 'html.png'
    def view(self, context):
        context.styles.append('/ui/wiki/style.css')
        parent = self.parent
        here = context.object

        # Decorate the links and resolve them against the published object
        document = self.get_document()
        for node in document.traverse(condition=nodes.reference):
            refname = node.get('wiki_name')
            if refname is None:
                # Regular link
                if node.get('refid'):
                    node['classes'].append('internal')
                refuri = node.get('refuri')
                if refuri is not None:
                    reference = get_reference(refuri.encode('utf_8'))
                    # Skip external
                    if reference.scheme or reference.authority:
                        node['classes'].append('external')
                        continue
                    try:
                        object = self.get_object(reference.path)
                        node['refuri'] = str(here.get_pathto(object))
                    except LookupError:
                        pass
            elif refname is False:
                    # Wiki link not found
                    node['classes'].append('nowiki')
                    prefix = here.get_pathto(parent)
                    title = node['name']
                    title_encoded = title.encode('utf_8')
                    params = {'type': self.__class__.__name__,
                              'title': title_encoded,
                              'name': checkid(title) or title_encoded}
                    refuri = "%s/;new_resource_form?%s" % (prefix,
                                                           urlencode(params))
                    node['refuri'] = refuri
            else:
                # Wiki link found, "refname" is the path
                node['classes'].append('wiki')
                object = self.get_object(refname)
                node['refuri'] = str(here.get_pathto(object))

        # Manipulate publisher directly (from publish_from_doctree)
        reader = Reader(parser_name='null')
        pub = Publisher(reader, None, None, source=DocTreeInput(document),
                destination_class=StringOutput)
        pub.set_writer('html')
        pub.process_programmatic_settings(None, self.overrides, None)
        pub.set_destination(None, None)
        pub.publish(enable_exit_status=None)
        parts = pub.writer.parts
        body = parts['html_body']

        return body.encode('utf_8')


    #######################################################################
    # UI / PDF
    #######################################################################
    to_pdf__access__ = 'is_allowed_to_view'
    to_pdf__label__ = u"View"
    to_pdf__sublabel__ = u"PDF"
    to_pdf__icon__ = 'pdf.png'
    def to_pdf(self, context):
        parent = self.parent
        pages = [self.get_abspath()]
        images = []

        document = self.get_document()
        # We hack a bit the document tree to enhance the PDF produced
        for node in document.traverse(condition=nodes.reference):
            refname = node.get('wiki_name')
            if refname is None:
                # Regular link: point back to the site
                refuri = node.get('refuri')
                if refuri is not None:
                    reference = get_reference(refuri.encode('utf_8'))
                    if isinstance(reference, Mailto):
                        # mailto:
                        node['refuri'] = str(reference)
                    else:
                        # Make canonical URI to the website for future download
                        node['refuri'] = str(context.uri.resolve(reference))
                continue
            # Now consider the link is valid
            title = node['name']
            document.nameids[title.lower()] = checkid(title)
            # The journey ends here for broken links
            if refname is False:
                continue
            # We extend the main page with the first level of subpages
            object = self.get_object(refname)
            abspath = object.get_abspath()
            if abspath not in pages:
                if not isinstance(object, WikiPage):
                    # Link to a file, set the URI to download it
                    prefix = context.object.get_pathto(object)
                    node['refuri'] = str(context.uri.resolve(prefix))
                    continue
                # Adding the page to this one
                subdoc = object.get_document()
                # We point the second level of links to the website
                for node in subdoc.traverse(condition=nodes.reference):
                    refname = node.get('wiki_name')
                    if refname is None:
                        # Regular link: point back to the site
                        refuri = node.get('refuri')
                        if refuri is not None:
                            reference = get_reference(refuri.encode('utf_8'))
                            node['refuri'] = str(context.uri.resolve(reference))
                        continue
                    # Now consider the link is valid
                    title = node['name']
                    refid = title.lower()
                    if refid not in document.nameids:
                        document.nameids[refid] = checkid(title)
                    # The journey ends here for broken links
                    if refname is False:
                        continue
                    object = self.get_object(refname)
                    prefix = context.object.get_pathto(object)
                    node['refuri'] = str(context.uri.resolve(prefix))
                # Now include the page
                # A page may begin with a section or a list of sections
                if len(subdoc) and isinstance(subdoc[0], nodes.section):
                    for node in subdoc.children:
                        if isinstance(node, nodes.section):
                            document.append(node)
                else:
                    subtitle = subdoc.get('title', u'')
                    section = nodes.section(*subdoc.children,
                                            **subdoc.attributes)
                    section.insert(0, nodes.title(text=subtitle))
                    document.append(section)
                pages.append(abspath)

        # Find the list of images to append
        for node in document.traverse(condition=nodes.image):
            uri = node['uri'].encode('utf_8')
            reference = get_reference(uri)
            if reference.scheme or reference.authority:
                # Fetch external image
                try:
                    image = get_handler(reference)
                    filename = reference.path.get_name()
                    name, ext, lang = FileName.decode(filename)
                    # At least images from ikaaro won't have an extension
                    if ext is None:
                        mimetype = vfs.get_mimetype(reference)
                        ext = guess_extension(mimetype)[1:]
                        filename = FileName.encode((name, ext, lang))
                except LookupError:
                    image = None
            else:
                try:
                    image = parent.get_object(reference.path)
                    filename = image.get_property('filename')
                except LookupError:
                    image = None
            if image is None:
                # Missing image, prevent pdfLaTeX failure
                image = self.get_object('/ui/wiki/missing.png')
                filename = image.name
                # Remove all path so the image is found in tempdir
                node['uri'] = filename
                images.append((image, filename))
            else:
                # pdflatex does not support the ".jpeg" extension
                name, ext, lang = FileName.decode(filename)
                if ext == 'jpeg':
                    filename = FileName.encode((name, 'jpg', lang))
                # Remove all path so the image is found in tempdir
                node['uri'] = filename
                images.append((image, filename))

        overrides = dict(self.overrides)
        overrides['stylesheet'] = 'style.tex'
        output = publish_from_doctree(document, writer_name='latex',
                settings_overrides=overrides)

        dirname = mkdtemp('wiki', 'itools')
        tempdir = vfs.open(dirname)

        # Save the document...
        file = tempdir.make_file(self.name)
        try:
            file.write(output)
        finally:
            file.close()
        # The stylesheet...
        stylesheet = self.get_object('/ui/wiki/style.tex')
        file = tempdir.make_file('style.tex')
        try:
            stylesheet.save_state_to_file(file)
        finally:
            file.close()
        # The 'powered' image...
        image = self.get_object('/ui/images/ikaaro_powered.png')
        file = tempdir.make_file('ikaaro.png')
        try:
            image.save_state_to_file(file)
        finally:
            file.close()
        # And referenced images
        for image, filename in images:
            if tempdir.exists(filename):
                continue
            file = tempdir.make_file(filename)
            try:
                if isinstance(image, FileHandler):
                    try:
                        image.save_state_to_file(file)
                    except XMLError:
                        # XMLError is raised by unexpected HTTP responses
                        # from external images. See bug #249
                        pass
                else:
                    image.handler.save_state_to_file(file)
            finally:
                file.close()

        try:
            call(['pdflatex', '-8bit', '-no-file-line-error',
                  '-interaction=batchmode', self.name], cwd=dirname)
            # Twice for correct page numbering
            call(['pdflatex', '-8bit', '-no-file-line-error',
                  '-interaction=batchmode', self.name], cwd=dirname)
        except OSError:
            msg = u"PDF generation failed. Please install pdflatex."
            return context.come_back(msg)

        pdfname = '%s.pdf' % self.name
        if tempdir.exists(pdfname):
            file = tempdir.open(pdfname)
            try:
                data = file.read()
            finally:
                file.close()
        else:
            data = None
        vfs.remove(dirname)

        if data is None:
            return context.come_back(u"PDF generation failed.")

        response = context.response
        response.set_header('Content-Type', 'application/pdf')
        response.set_header('Content-Disposition',
                'attachment; filename=%s' % pdfname)

        return data


    #######################################################################
    # UI / Edit
    #######################################################################
    def edit_form(self, context):
        context.styles.append('/ui/wiki/style.css')
        context.scripts.append('/ui/wiki/javascript.js')
        text_size = context.get_form_value('text_size');
        text_size_cookie = context.get_cookie('wiki_text_size')

        if text_size_cookie is None:
            if not text_size:
                text_size = 'small'
            context.set_cookie('wiki_text_size', text_size)
        elif text_size is None:
            text_size = context.get_cookie('wiki_text_size')
        elif text_size != text_size_cookie:
            context.set_cookie('wiki_text_size', text_size)

        namespace = {}
        namespace['timestamp'] = DateTime.encode(datetime.now())
        data = context.get_form_value('data') or self.handler.to_str()
        namespace['data'] = data
        namespace['text_size'] = text_size

        handler = self.get_object('/ui/wiki/WikiPage_edit.xml')
        return stl(handler, namespace)


    def edit(self, context):
        timestamp = context.get_form_value('timestamp', type=DateTime)
        if timestamp is None:
            return context.come_back(MSG_EDIT_CONFLICT)
        page = self.handler
        if page.timestamp is not None and timestamp < page.timestamp:
            return context.come_back(MSG_EDIT_CONFLICT)

        # Data is assumed to be encoded in UTF-8
        data = context.get_form_value('data')

        # Validate data by compiling it
        try:
            html = publish_string(data, writer_name='html',
                                  settings_overrides=self.overrides)
        except SystemMessage, message:
            # Critical error
            msg = u"A syntax error prevented from saving the changes: $error"
            # docutils is using tags to represent the error
            error = XML.encode(message.message)
            return context.come_back(msg, error=error,
                                     keep=['data', 'text_size'])

        # OK, committing
        page.load_state_from_string(data)
        context.server.change_object(self)

        # But warn about non-critical syntax errors
        if 'class="system-message"' in self.view(context):
            message = u"Syntax error, please check the view for details."
        else:
            message = MSG_CHANGES_SAVED

        # Come back to the desired view
        goto = context.come_back(message, keep=['text_size'])
        if context.has_form_value('view'):
            query = goto.query
            goto = goto.resolve(';view')
            goto.query = query
        else:
            goto.fragment = 'bottom'
        return goto


    #######################################################################
    # UI / Help
    #######################################################################
    help__access__ = 'is_allowed_to_view'
    help__label__ = u"Help"
    help__icon__ = 'help.png'
    def help(self, context):
        context.styles.append('/ui/wiki/style.css')
        namespace = {}

        source = self.get_object('/ui/wiki/help.txt')
        source = source.to_str()
        html = publish_string(source, writer_name='html',
                settings_overrides=self.overrides)

        namespace['help_source'] = source
        namespace['help_html'] = XMLParser(html)

        handler = self.get_object('/ui/wiki/WikiPage_help.xml')
        return stl(handler, namespace)


    #######################################################################
    # Update
    #######################################################################
    def update_20071216(self):
        # Names are lower-case now
        name = self.name
        if self.name != 'FrontPage':
            name = checkid(name)
        # Rename metadata
        folder = self.parent.handler
        if name != self.name:
            folder.move_handler('%s.metadata' % self.name,
                                '%s.metadata' % name)
        # Rename handler
        folder.move_handler(self.name, '%s.txt' % name)


    def update_20071217(self):
        handler = self.handler
        data = handler.data
        total = 0
        document = self.get_document()

        # Links
        for node in document.traverse(condition=nodes.reference):
            refname = node.get('wiki_name')
            if refname is False:
                link = node['name']
                name, type, language = FileName.decode(link)
                if type is not None:
                    data, n = subn(u'`%s`_' % link, u'`%s`_' % name, data)
                    total += n

        # Images
        for node in document.traverse(condition=nodes.image):
            refname = node['uri']
            if self.resolve_link(refname) is None:
                link = refname
                name, type, language = FileName.decode(link)
                if type is not None:
                    data, n = subn(link, name, data)
                    total += n

        # Commit
        if total > 0:
            handler.set_data(data)



###########################################################################
# Register
###########################################################################
register_object_class(WikiPage)
