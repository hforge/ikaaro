# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2008 Hervé Cauwelier <herve@itaapy.com>
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
from os.path import splitext

# Import from itools
from itools.datatypes import Boolean, HTTPDate, PathDataType, String
from itools.fs import FileName
from itools.gettext import MSG
from itools.web import BaseView, STLView, ERROR, FormError

# Import from ikaaro
from autoadd import AutoAdd
from autoedit import AutoEdit
from autoform import PathSelectorWidget
from autoform import ReadOnlyWidget
from fields import ProgressBar_Field
from folder import Folder
from messages import MSG_NAME_CLASH, MSG_NEW_RESOURCE


class File_NewInstance(AutoAdd):

    title = MSG(u'Upload File')
    fields = ['data', 'title', 'state', 'location', 'progressbar']

    progressbar = ProgressBar_Field

    def get_new_resource_name(self, form):
        name = super(File_NewInstance, self).get_new_resource_name(form)
        if name:
            return name

        filename, mimetype, body = form['data']
        name, type, language = FileName.decode(filename)
        return name


    def action(self, resource, context, form):
        # 1. Make the resource
        container = form['container']
        name = form['name']
        filename, mimetype, body = form['data']
        language = container.get_edit_languages(context)[0]
        child = container._make_file(name, filename, mimetype, body, language)
        # 2. Set properties
        self.set_value(child, context, 'title', form)
        self.set_value(child, context, 'state', form)
        # Ok
        goto = str(resource.get_pathto(child))
        return context.come_back(MSG_NEW_RESOURCE, goto=goto)



class File_View(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'Download')
    icon = 'view.png'
    template = '/ui/file/download_form.xml'


    def get_namespace(self, resource, context):
        filename = resource.get_value('filename') or resource.get_title()
        return {'filename': filename}



class File_Edit(AutoEdit):

    fields = ['title', 'state', 'data', 'description', 'subject']
    def _get_widget(self, resource, context, name):
        widget = super(File_Edit, self)._get_widget(resource, context, name)

        if name == 'state':
            root = context.root
            user = context.user
            if not root.has_permission(user, 'change_state', resource):
                return ReadOnlyWidget(name, title=widget.title)

        return widget



class File_ExternalEdit_View(STLView):
    access = 'is_allowed_to_edit'
    template = '/ui/file/externaledit.xml'
    title = MSG(u'External Editor')
    icon = 'external.png'




class File_ExternalEdit(BaseView):

    access = 'is_allowed_to_edit'


    def GET(self, resource, context):
        """Protocol used (with restedit.py):
        1- We add a header to the content of the file
        2- The header is separated from the rest of the file by a "\n\n".
        3- An entry in the header is:

           header-name:header-body\n

           The header-name does not contain ":" and the header-body does not
           contain "\n"
        4- Everything is sent in utf-8
        """
        uri = context.uri
        handler = resource.handler
        header = [
            'url:%s://%s%s' % (uri.scheme, uri.authority, uri.path[:-1]),
            'last-modified:%s' % HTTPDate.encode(handler.get_mtime()),
            'content_type:%s' % handler.get_mimetype(),
            'title:%s' % resource.get_title().encode('utf-8'),
            'include-Cookie:iauth="%s"' % context.get_cookie('iauth'),
            'include-X-User-Agent:%s' % context.get_header('User-Agent')]

        # Try to guess the extension (optional)
        filename = resource.get_value('filename')
        if filename:
            extension = splitext(filename)[1]
            if extension:
                extension = extension[1:]
                if extension in resource.get_all_extensions():
                    # All OK
                    header.append('extension:.%s' % extension)

        # Authorization part
        auth = context.get_header('Authorization')
        if auth:
            header.append('auth:%s' % auth)

        # Add the "\n\n" and make the header
        header.append('\n')
        header = '\n'.join(header)
        data = handler.to_str()

        # TODO known bug from ExternalEditor requires rfc1123_date()
        # Using RESPONSE.setHeader('Pragma', 'no-cache') would be better, but
        # this chokes crappy most MSIE versions when downloads happen on SSL.
        # cf. http://support.microsoft.com/support/kb/articles/q316/4/31.asp
        #context.set_header('Last-Modified', rfc1123_date())
        context.set_header('Pragma', 'no-cache')
        context.content_type = 'application/x-restedit'
        context.set_content_disposition('inline', '%s.restedit' %
                                        resource.name)
        return header + data



class Image_View(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    template = '/ui/binary/Image_view.xml'
    styles = ['/ui/gallery/style.css']

    # Image default size as a string (empty = full size)
    query_schema = {
        'size': String(default='800x600')}

    sizes = [
        ('640x480', u"small"),
        ('800x600', u"medium"),
        ('1024x768', u"large"),
        ('1280x1024', u"huge"),
        ('original', u"original")]


    def get_namespace(self, resource, context):
        size = context.query['size']
        if not size:
            size = self.get_query_schema()['size'].default

        # Menu
        widths = [
            {'size': x, 'title': title, 'selected': x == size}
            for (x, title) in self.sizes ]

        # img
        if size == 'original':
            link = ';download'
        else:
            try:
                width, height = size.split('x')
            except ValueError:
                width = height = size
            link = ';thumb?width=%s&height=%s' % (width, height)

        # Real width and height (displayed for reference)
        image_width, image_height = resource.get_value('data').get_size()
        return {'widths': widths,
                'link': link,
                'image_width': image_width,
                'image_height': image_height}



# FIXME This is broken, check http://alistapart.com/articles/byebyeembed
class Video_View(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    template = '/ui/binary/Video_view.xml'


    def get_namespace(self, resource, context):
        return {'format': resource.get_value('data').get_mimetype()}



class Archive_View(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    template = '/ui/binary/Archive_view.xml'

    schema = {'target': PathDataType, 'update': Boolean}

    def get_namespace(self, resource, context):
        filename = resource.get_value('filename') or resource.get_title()
        contents = resource.get_value('data').get_contents()
        contents = '\n'.join(contents)
        # Extract archive
        root = context.root
        extract = root.is_allowed_to_edit(context.user, resource)
        if extract:
            widget = PathSelectorWidget('target', value='..').render()
        else:
            widget = None
        # Ok
        return {'filename': filename, 'contents': contents,
                'extract': extract, 'widget': widget}


    def _get_form(self, resource, context):
        form = super(Archive_View, self)._get_form(resource, context)

        # Get the target resource
        target = form['target']
        target = resource.get_resource(target, soft=True)
        if target is None:
            raise FormError, ERROR(u'Target does not exist.')
        if isinstance(target, Folder) is False:
            raise FormError, ERROR(u'Target must be a folder.')

        return form


    def action(self, resource, context, form):
        # Get the list of paths to extract
        handler = resource.get_value('data')
        paths = handler.get_contents()
        paths.sort()

        # Get the target resource
        target = form['target']
        target = resource.get_resource(target)

        # Make the resources
        language = resource.get_edit_languages(context)[0]
        try:
            target.extract_archive(handler, language, update=form['update'])
        except RuntimeError, message:
            context.commit = False
            context.message = MSG_NAME_CLASH
            return

        # Ok
        message = MSG(u'Files extracted')
        goto = context.get_link(target)
        return context.come_back(message, goto=goto)



class Flash_View(File_View):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    template = '/ui/binary/Flash_view.xml'
