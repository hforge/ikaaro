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
from re import compile
from subprocess import call
from tempfile import mkdtemp
from urllib import urlencode

# Import from docutils
from docutils.core import Publisher, publish_from_doctree, publish_string
from docutils.io import StringOutput, DocTreeInput
from docutils.readers.doctree import Reader
from docutils.utils import SystemMessage
from docutils import nodes

# Import from itools
from itools.core import merge_dicts
from itools.datatypes import String, Unicode
from itools.gettext import MSG
from itools.handlers import checkid, ro_database
from itools.html import XHTMLFile
from itools.i18n import format_datetime
from itools.uri import get_reference
from itools.uri.mailto import Mailto
from itools.fs import lfs, FileName
from itools.web import view, stl_view, ERROR
from itools.xml import XMLParser, XMLError

# Import from ikaaro
from ikaaro.fields import NameField
from ikaaro import messages
from ikaaro.forms import title_widget, timestamp_widget
from ikaaro.resource_views import DBResource_Edit
from ikaaro.views_new import NewInstanceByDate



class WikiPage_NewInstance(NewInstanceByDate):

    name = NameField


    def get_new_resource_name(self):
        # If the name is not explicitly given, use the title
        name = self.name.value
        title = self.title.value.strip()
        return name or title


    def get_container(self):
        from folder import WikiFolder

        root = self.context.site_root
        wiki = root.get_resource('wiki', soft=True)
        if wiki is None:
            return root.make_resource('wiki', WikiFolder)
        return wiki


    def get_resource_class(self):
        from page import WikiPage
        return WikiPage



figure_style_converter = compile(r'\\begin\{figure\}\[.*?\]')


def is_external(reference):
    return (type(reference) is Mailto or reference.scheme
            or reference.authority)



def default_reference_resolver(resource, reference, context):
    """Make canonical URI to the website for future download.
    """
    # Resolve against the parent
    uri = context.uri.resolve('..')
    return str(uri.resolve2(reference))



def resolve_references(doctree, resource, context,
        reference_resolver=default_reference_resolver):
    """Translate resource path to handler uri.
    """
    for node in doctree.traverse(condition=nodes.reference):
        wiki_name = node.get('wiki_name')
        if wiki_name is False:
            # Broken link
            continue
        elif wiki_name:
            # Wiki link
            reference = get_reference(wiki_name)
            node['refuri'] = reference_resolver(resource, reference, context)
        elif wiki_name is None:
            # Regular link: point back to the site
            refuri = node.get('refuri')
            if refuri is None:
                continue
            reference = get_reference(refuri.encode('utf_8'))
            if is_external(reference):
                # Keep the unicode version
                continue
            node['refuri'] = reference_resolver(resource, reference, context)



def resolve_images(doctree, resource, context):
    """Translate image path to handler uri.
    """
    for node in doctree.traverse(condition=nodes.image):
        reference = get_reference(node['uri'].encode('utf8'))
        if is_external(reference):
            continue
        name = str(reference.path)
        image = resource.get_resource(name, soft=True)
        if image is not None:
            node['uri'] = image.handler.key



class WikiPage_View(view):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    icon = 'html.png'
    styles = ['/ui/wiki/style.css']


    def GET(self, resource, context):
        parent = resource.get_parent()

        try:
            doctree = resource.get_doctree()
        except SystemMessage, e:
            # Critical
            context.message = ERROR(u'Syntax error: {error}',
                    error=e.message)
            return XMLParser('<pre>' + resource.handler.to_str() + '</pre>')

        # Decorate the links and resolve them against the published resource
        for node in doctree.traverse(condition=nodes.reference):
            refname = node.get('wiki_name')
            if refname is None:
                # Regular link
                if node.get('refid'):
                    node['classes'].append('internal')
                refuri = node.get('refuri')
                if refuri is None:
                    continue
                reference = get_reference(refuri.encode('utf_8'))
                # Skip external
                if is_external(reference):
                    node['classes'].append('external')
                    continue
                destination = resource.get_resource(reference.path,
                        soft=True)
                if destination is None:
                    continue
                refuri = context.get_link(destination)
                if reference.fragment:
                    refuri = "%s#%s" % (refuri, reference.fragment)
                node['refuri'] = refuri
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

        # Download images directly
        for node in doctree.traverse(condition=nodes.image):
            reference = get_reference(node['uri'].encode('utf_8'))
            if is_external(reference):
                continue
            destination = resource.get_resource(reference.path, soft=True)
            if destination is None:
                continue
            node['uri'] = '%s/;download' % context.get_link(destination)

        # Manipulate publisher directly (from publish_from_doctree)
        reader = Reader(parser_name='null')
        pub = Publisher(reader, None, None, source=DocTreeInput(doctree),
                destination_class=StringOutput)
        pub.set_writer('html')
        pub.process_programmatic_settings(None, resource.overrides, None)
        pub.set_destination(None, None)
        pub.publish(enable_exit_status=None)
        parts = pub.writer.parts
        body = parts['html_body']

        return body.encode('utf_8')



class WikiPage_ToPDF(view):

    access = 'is_allowed_to_view'
    title = MSG(u"To PDF")


    def GET(self, resource, context):
        # Check if pdflatex exists
        try:
            call(['pdflatex', '-version'])
        except OSError:
            msg = ERROR(u"PDF generation failed. Please install pdflatex on "
                    u"the server.")
            return context.come_back(msg)

        doctree = resource.get_doctree()
        # We hack a bit the document tree to enhance the PDF produced
        resolve_references(doctree, resource, context)
        resolve_images(doctree, resource, context)

        # Make some modifications
        overrides = dict(resource.overrides)
        overrides['stylesheet'] = 'style.tex'
        output = publish_from_doctree(doctree, writer_name='latex',
                                      settings_overrides=overrides)
        output = figure_style_converter.sub(r'\\begin{figure}[H]', output)

        dirname = mkdtemp('wiki', 'itools')
        tempdir = lfs.open(dirname)

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
        # The stub for not found images
        stub = resource.get_resource('/ui/wiki/missing.png')
        # And referenced images
        for node in doctree.traverse(condition=nodes.image):
            uri = node['uri']
            filename = uri.rsplit('/', 1)[-1]
            # pdflatex does not support the ".jpeg" extension
            name, ext, lang = FileName.decode(filename)
            if ext == 'jpeg':
                filename = FileName.encode((name, 'jpg', lang))
            if tempdir.exists(filename):
                continue
            file = tempdir.make_file(filename)
            try:
                try:
                    handler = ro_database.get_handler(uri)
                except LookupError:
                    handler = stub
                try:
                    handler.save_state_to_file(file)
                except XMLError:
                    # XMLError is raised by unexpected HTTP responses
                    # from external images. See bug #249
                    pass
            finally:
                file.close()
            # Remove all path so the image is found in tempdir
            node['uri'] = filename

        # From LaTeX to PDF
        command = ['pdflatex', '-8bit', '-no-file-line-error',
                   '-interaction=batchmode', resource.name]
        try:
            call(command, cwd=dirname)
            # Twice for correct page numbering
            call(command, cwd=dirname)
        except OSError:
            msg = ERROR(u'PDF generation failed. See "{dirname}" on the '
                    u'server for debug.', dirname=dirname)
            return context.come_back(msg)

        pdfname = '%s.pdf' % resource.name
        if not tempdir.exists(pdfname):
            msg = ERROR(u'PDF generated not found. See "{dirname}" on the '
                    u'server for debug.', dirname=dirname)
            return context.come_back(msg)

        # Read the file's data
        file = tempdir.open(pdfname)
        try:
            data = file.read()
        finally:
            file.close()

        # Clean the temporary folder
        lfs.remove(dirname)

        # Ok
        context.set_content_type('application/pdf')
        context.set_content_disposition('inline', pdfname)
        return data



# TODO Use auto-form
class WikiPage_Edit(DBResource_Edit):

    template = '/ui/wiki/edit.xml'
    schema = merge_dicts(DBResource_Edit.schema, data=String)
    widgets = [timestamp_widget, title_widget]

    # No Multilingual
    context_menus = []

    styles = ['/ui/tiny_mce/themes/advanced/skins/default/ui.css',
              '/ui/wiki/style.css']
    scripts = ['/ui/tiny_mce/tiny_mce_src.js',
               '/ui/wiki/javascript.js']


    def get_namespace(self, resource, context):
        namespace = DBResource_Edit.get_namespace(self, resource, context)
        namespace['data'] = (context.get_form_value('data') or
                resource.handler.to_str())
        return namespace


    def action_save(self, resource, context, form):
        DBResource_Edit.action(self, resource, context, form)
        if self.edit_conflict:
            return

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
            message = ERROR(u'Syntax error: {error}', error=e.message)
        if message is None:
            accept = context.accept_language
            time = format_datetime(datetime.now(), accept=accept)
            message = messages.MSG_CHANGES_SAVED2(time=time)

        context.message = message


    def action_save_and_view(self, resource, context, form):
        self.action_save(resource, context, form)
        goto = context.come_back(context.message)
        query = goto.query
        goto = goto.resolve(';view')
        goto.query = query
        return goto



class WikiPage_Help(stl_view):

    access = 'is_allowed_to_view'
    title = MSG(u"Help")
    template = '/ui/wiki/help.xml'
    styles = ['/ui/wiki/style.css']


    def get_namespace(self, resource, context):
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
