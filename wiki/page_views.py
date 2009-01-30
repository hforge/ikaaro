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
from datetime import datetime
from tempfile import mkdtemp
from subprocess import call
from urllib import urlencode
from re import compile

# Import from docutils
from docutils.core import Publisher, publish_from_doctree, publish_string
from docutils.io import StringOutput, DocTreeInput
from docutils.readers.doctree import Reader
from docutils.utils import SystemMessage
from docutils import nodes

# Import from itools
from itools import vfs
from itools.datatypes import DateTime, String, Unicode
from itools.gettext import MSG
from itools.handlers import checkid, get_handler, File as FileHandler
from itools.html import XHTMLFile
from itools.i18n import format_datetime
from itools.uri import get_reference
from itools.uri.mailto import Mailto
from itools.utils import guess_extension
from itools.vfs import FileName
from itools.web import BaseView, STLForm, STLView, ERROR
from itools.xml import XMLParser, XMLError

# Import from ikaaro
from ikaaro import messages
from ikaaro.html import is_edit_conflict


figure_style_converter = compile(r'\\begin\{figure\}\[.*?\]')

class WikiPage_View(BaseView):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    icon = 'html.png'


    def GET(self, resource, context):
        context.styles.append('/ui/wiki/style.css')
        parent = resource.parent

        try:
            document = resource.get_document()
        except SystemMessage, e:
            # Critical
            context.message = ERROR(u'Syntax error: $error', error=e.message)
            return XMLParser('<pre>' + resource.handler.to_str() + '</pre>')

        # Decorate the links and resolve them against the published resource
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
                        destination = resource.get_resource(reference.path)
                        node['refuri'] = context.get_link(destination)
                    except LookupError:
                        pass
            elif refname is False:
                    # Wiki link not found
                    node['classes'].append('nowiki')
                    prefix = resource.get_pathto(parent)
                    title = node['name']
                    title_encoded = title.encode('utf_8')
                    params = {'type': resource.__class__.__name__,
                              'title': title_encoded,
                              'name': checkid(title) or title_encoded}
                    refuri = "%s/;new_resource?%s" % (prefix,
                                                      urlencode(params))
                    node['refuri'] = refuri
            else:
                # Wiki link found, "refname" is the path
                node['classes'].append('wiki')
                destination = resource.get_resource(refname)
                node['refuri'] = context.get_link(destination)

        # Manipulate publisher directly (from publish_from_doctree)
        reader = Reader(parser_name='null')
        pub = Publisher(reader, None, None, source=DocTreeInput(document),
                destination_class=StringOutput)
        pub.set_writer('html')
        pub.process_programmatic_settings(None, resource.overrides, None)
        pub.set_destination(None, None)
        pub.publish(enable_exit_status=None)
        parts = pub.writer.parts
        body = parts['html_body']

        return body.encode('utf_8')



class WikiPage_ToPDF(BaseView):

    access = 'is_allowed_to_view'
    title = MSG(u"To PDF")


    def GET(self, resource, context):
        parent = resource.parent
        pages = [resource.get_abspath()]
        images = []

        document = resource.get_document()
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
                        # Make canonical URI to the website for future
                        # download
                        node['refuri'] = str(context.uri.resolve(reference))
                continue
            # Now consider the link is valid
            title = node['name']
            document.nameids[title.lower()] = checkid(title)
            # The journey ends here for broken links
            if refname is False:
                continue
            # We extend the main page with the first level of subpages
            destination = resource.get_resource(refname)
            abspath = destination.get_abspath()
            if abspath not in pages:
                from page import WikiPage
                if not isinstance(destination, WikiPage):
                    # Link to a file, set the URI to download it
                    prefix = context.resource.get_pathto(destination)
                    node['refuri'] = str(context.uri.resolve(prefix))
                    continue
                # Adding the page to this one
                subdoc = destination.get_document()
                # We point the second level of links to the website
                for node in subdoc.traverse(condition=nodes.reference):
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
                                refuri = context.uri.resolve(reference)
                                node['refuri'] = str(refuri)
                        continue
                    # Now consider the link is valid
                    title = node['name']
                    refid = title.lower()
                    if refid not in document.nameids:
                        document.nameids[refid] = checkid(title)
                    # The journey ends here for broken links
                    if refname is False:
                        continue
                    destination = resource.get_resource(refname)
                    prefix = context.resource.get_pathto(destination)
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

            # Hack to handle local images
            reference = get_reference(uri)
            if not reference.scheme and uri.endswith('/;download'):
                reference = get_reference(uri[:-len('/;download')])

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
                    image = parent.get_resource(reference.path)
                    filename = image.get_property('filename')
                except LookupError:
                    image = None
            if image is None:
                # Missing image, prevent pdfLaTeX failure
                image = resource.get_resource('/ui/wiki/missing.png')
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

        # Make some modifications
        overrides = dict(resource.overrides)
        overrides['stylesheet'] = 'style.tex'
        output = publish_from_doctree(document, writer_name='latex',
                                      settings_overrides=overrides)
        output = figure_style_converter.sub(r'\\begin{figure}[H]', output)

        dirname = mkdtemp('wiki', 'itools')
        tempdir = vfs.open(dirname)

        # Save the document...
        file = tempdir.make_file(resource.name)
        try:
            file.write(output)
        finally:
            file.close()
        # The stylesheet...
        stylesheet = resource.get_resource('/ui/wiki/style.tex')
        file = tempdir.make_file('style.tex')
        try:
            stylesheet.save_state_to_file(file)
        finally:
            file.close()
        # The 'powered' image...
        image = resource.get_resource('/ui/aruni/images/ikaaro_powered.png')
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

        # From latex to PDF
        command = ['pdflatex', '-8bit', '-no-file-line-error',
                   '-interaction=batchmode', resource.name]
        try:
            call(command, cwd=dirname)
            # Twice for correct page numbering
            call(command, cwd=dirname)
        except OSError:
            msg = ERROR(u"PDF generation failed. Please install pdflatex.")
            return context.come_back(msg)

        pdfname = '%s.pdf' % resource.name
        if not tempdir.exists(pdfname):
            # TODO Print an error message somewhere with the 'dirname' for
            # inspection of the problem.
            return context.come_back(MSG(u"PDF generation failed."))

        # Read the file's data
        file = tempdir.open(pdfname)
        try:
            data = file.read()
        finally:
            file.close()

        # Clean the temporary folder
        vfs.remove(dirname)

        # Ok
        response = context.response
        response.set_header('Content-Type', 'application/pdf')
        response.set_header('Content-Disposition',
                            'attachment; filename=%s' % pdfname)
        return data



class WikiPage_Edit(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit Page')
    template = '/ui/wiki/edit.xml'
    schema = {
        'title': Unicode,
        'data': String,
        'timestamp': DateTime,
    }


    def get_namespace(self, resource, context):
        context.styles.append(
                '/ui/tiny_mce/themes/advanced/skins/default/ui.css')
        context.styles.append('/ui/wiki/style.css')
        context.scripts.append('/ui/tiny_mce/tiny_mce_src.js')
        context.scripts.append('/ui/wiki/javascript.js')

        data = context.get_form_value('data') or resource.handler.to_str()
        return {
            'title': resource.get_title(),
            'data': data,
            'timestamp': DateTime.encode(datetime.now()),
        }


    def action(self, resource, context, form):
        if is_edit_conflict(resource, context, form['timestamp']):
            return

        title = form['title']
        language = resource.get_content_language(context)
        resource.set_property('title', title, language=language)

        # Data is assumed to be encoded in UTF-8
        data = form['data']
        # Save even if broken
        resource.handler.load_state_from_string(data)

        # Warn about syntax errors
        message = None
        try:
            html = resource.view.GET(resource, context)
            # Non-critical
            if 'class="system-message"' in html:
                message = ERROR(u"Syntax error, please check the view for "
                                u"details.")
        except SystemMessage, e:
            # Critical
            message = ERROR(u'Syntax error: $error', error=e.message)
        if message is None:
            accept = context.accept_language
            time = format_datetime(datetime.now(), accept=accept)
            message = messages.MSG_CHANGES_SAVED2(time=time)

        # Come back to the desired view
        if context.has_form_value('view'):
            goto = context.come_back(message)
            query = goto.query
            goto = goto.resolve(';view')
            goto.query = query
            return goto

        context.message = message



class WikiPage_Help(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u"Help")
    template = '/ui/wiki/help.xml'


    def get_namespace(self, resource, context):
        context.styles.append('/ui/wiki/style.css')

        source = resource.get_resource('/ui/wiki/help.txt')
        source = source.to_str()

        overrides = dict(resource.overrides)
        overrides['stylesheet'] = ''
        html = publish_string(source, writer_name='html',
                               settings_overrides=overrides)
        document = XHTMLFile(string=html)
        events = document.get_body().get_content_elements()

        # Now remove some magic to make the help work like a wiki page
        source = source.split('.. XXX SPLIT HERE')[0]

        return {
            'help_source': source,
            'help_html': events,
        }
