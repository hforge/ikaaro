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
from datetime import datetime

# Import from itools
from itools.datatypes import String
from itools.gettext import MSG
from itools.handlers import File as FileHandler, Image as ImageHandler
from itools.handlers import TARFile, ZIPFile, GzipFile, Bzip2File
from itools.odf import SXWFile, SXCFile, SXIFile, ODTFile, ODSFile, ODPFile
from itools.pdf import PDFFile
from itools.utils import guess_all_extensions
from itools.vfs import FileName
from itools.web import STLView
from itools.xml import MSPowerPoint as MSPowerPointFile, RTF as RTFFile
from itools.xml import MSWord as MSWordFile, MSExcel as MSExcelFile

# Import from ikaaro
from registry import register_resource_class
from versioning import VersioningAware
from workflow import WorkflowAware
from file_views import File_NewInstance, File_Download, File_View
from file_views import File_Edit, File_ExternalEdit, File_Backlinks
from file_views import Image_Thumbnail, Image_View, Video_View, Archive_View
from file_views import Flash_View



###########################################################################
# Base File
###########################################################################
class File(WorkflowAware, VersioningAware):

    class_id = 'file'
    class_version = '20071216'
    class_title = MSG(u'File')
    class_description = MSG(
        u'Upload office documents, images, media files, etc.')
    class_icon16 = 'icons/16x16/file.png'
    class_icon48 = 'icons/48x48/file.png'
    class_views = ['view', 'edit', 'externaledit', 'upload', 'backlinks',
                   'edit_state', 'history']
    class_handler = FileHandler


    @staticmethod
    def _make_resource(cls, folder, name, body=None, filename=None,
                     extension=None, **kw):
        VersioningAware._make_resource(cls, folder, name, filename=filename,
                                       **kw)
        # Add the body
        if body is not None:
            handler = cls.class_handler(string=body)
            if extension:
                extension = extension.lower()
            else:
                extension = handler.class_extension
            name = FileName.encode((name, extension, None))
            folder.set_handler(name, handler)


    def get_all_extensions(self):
        format = self.metadata.format
        # FIXME This is a hack, compression encodings are not yet properly
        # supported (to do for the next major version).
        if format == 'application/x-gzip':
            extensions = ['gz', 'tgz']
        elif format == 'application/x-bzip2':
            extensions = ['bz2', 'tbz2']
        else:
            cls = self.class_handler
            extensions = [ x[1:] for x in guess_all_extensions(format) ]
            if cls.class_extension in extensions:
                extensions.remove(cls.class_extension)
            extensions.insert(0, cls.class_extension)
        return extensions


    def get_handler(self):
        # Already loaded
        if self._handler is not None:
            return self._handler

        # Not yet loaded
        database = self.metadata.database
        base = self.metadata.uri
        cls = self.class_handler

        # Check the handler exists
        extensions = self.get_all_extensions()
        for extension in extensions:
            name = FileName.encode((self.name, extension, None))
            uri = base.resolve(name)
            # Found
            if database.has_handler(uri):
                self._handler = database.get_handler(uri, cls=cls)
                return self._handler

        # Not found, build a dummy one
        name = FileName.encode((self.name, cls.class_extension, None))
        uri = base.resolve(name)
        handler = cls()
        handler.database = database
        handler.uri = uri
        handler.timestamp = None
        handler.dirty = datetime.now()
        database.add_to_cache(uri, handler)
        self._handler = handler
        return self._handler

    handler = property(get_handler, None, None, '')


    def rename_handlers(self, new_name):
        folder = self.parent.handler
        old_name = self.name
        for extension in self.get_all_extensions():
            old = FileName.encode((old_name, extension, None))
            if folder.has_handler(old):
                return [(old, FileName.encode((new_name, extension, None)))]
        return None, None


    #######################################################################
    # Metadata
    #######################################################################
    @classmethod
    def get_metadata_schema(cls):
        schema = VersioningAware.get_metadata_schema()
        schema.update(WorkflowAware.get_metadata_schema())
        schema['filename'] = String
        return schema


    #######################################################################
    # Versioning & Indexing
    #######################################################################
    def to_text(self):
        return self.handler.to_text()


    def get_size(self):
        sizes = [ len(x.to_str()) for x in self.get_handlers() ]
        # XXX Maybe not the good algo
        return max(sizes)


    #######################################################################
    # User Interface
    #######################################################################
    def get_human_size(self):
        file = self.handler
        bytes = len(file.to_str())
        size = bytes / 1024.0
        if size >= 1024:
            size = size / 1024.0
            str = MSG(u'%.01f MB')
        else:
            str = MSG(u'%.01f KB')

        return str.gettext() % size


    def get_content_type(self):
        return self.handler.get_mimetype()

    # Views
    new_instance = File_NewInstance()
    download = File_Download()
    view = File_View()
    edit = File_Edit()
    externaledit = STLView(
        access='is_allowed_to_edit',
        title=MSG(u'External Editor'),
        icon='external.png',
        template='/ui/file/externaledit.xml')
    external_edit = File_ExternalEdit()
    backlinks = File_Backlinks()



###########################################################################
# Media
###########################################################################
class Image(File):
    class_id = 'image'
    class_version = '20071216'
    class_title = MSG(u'Image')
    class_icon16 = 'icons/16x16/image.png'
    class_icon48 = 'icons/48x48/image.png'
    class_views = ['view', 'download', 'edit', 'externaledit', 'upload',
                   'backlinks', 'edit_state', 'history']
    class_handler = ImageHandler

    # Views
    thumb = Image_Thumbnail()
    view = Image_View()



class Video(File):
    class_id = 'video'
    class_version = '20071216'
    class_title = MSG(u'Video')
    class_description = MSG(u'Video')
    class_icon16 = 'icons/16x16/flash.png'
    class_icon48 = 'icons/48x48/flash.png'

    # Views
    view = Video_View()



class Flash(File):
    class_id = 'application/x-shockwave-flash'
    class_version = '20071216'
    class_title = MSG(u'Flash')
    class_description = MSG(u'Flash Document')
    class_icon16 = 'icons/16x16/flash.png'
    class_icon48 = 'icons/48x48/flash.png'

    # Views
    view = Flash_View()



###########################################################################
# Office Documents
###########################################################################
class MSWord(File):
    class_id = 'application/msword'
    class_version = '20071216'
    class_title = MSG(u'Word')
    class_description = MSG(u'Word Text')
    class_icon16 = 'icons/16x16/word.png'
    class_icon48 = 'icons/48x48/word.png'
    class_handler = MSWordFile



class MSExcel(File):
    class_id = 'application/vnd.ms-excel'
    class_version = '20071216'
    class_title = MSG(u'Excel')
    class_description = MSG(u'Excel Spreadsheet')
    class_icon16 = 'icons/16x16/excel.png'
    class_icon48 = 'icons/48x48/excel.png'
    class_handler = MSExcelFile



class MSPowerPoint(File):
    class_id = 'application/vnd.ms-powerpoint'
    class_version = '20071216'
    class_title = MSG(u'PowerPoint')
    class_description = MSG(u'PowerPoint Presentation')
    class_icon16 = 'icons/16x16/powerpoint.png'
    class_icon48 = 'icons/48x48/powerpoint.png'
    class_handler = MSPowerPointFile



class OOWriter(File):
    class_id = 'application/vnd.sun.xml.writer'
    class_version = '20071216'
    class_title = MSG(u'OOo Writer')
    class_description = MSG(u'OpenOffice.org Text')
    class_icon16 = 'icons/16x16/oowriter.png'
    class_icon48 = 'icons/48x48/oowriter.png'
    class_handler = SXWFile



class OOCalc(File):
    class_id = 'application/vnd.sun.xml.calc'
    class_version = '20071216'
    class_title = MSG(u'OOo Calc')
    class_description = MSG(u'OpenOffice.org Spreadsheet')
    class_icon16 = 'icons/16x16/oocalc.png'
    class_icon48 = 'icons/48x48/oocalc.png'
    class_handler = SXCFile



class OOImpress(File):
    class_id = 'application/vnd.sun.xml.impress'
    class_version = '20071216'
    class_title = MSG(u'OOo Impress')
    class_description = MSG(u'OpenOffice.org Presentation')
    class_icon16 = 'icons/16x16/ooimpress.png'
    class_icon48 = 'icons/48x48/ooimpress.png'
    class_handler = SXIFile



class PDF(File):
    class_id = 'application/pdf'
    class_version = '20071216'
    class_title = MSG(u'PDF')
    class_description = MSG(u'PDF Document')
    class_icon16 = 'icons/16x16/pdf.png'
    class_icon48 = 'icons/48x48/pdf.png'
    class_handler = PDFFile



class RTF(File):
    class_id = 'text/rtf'
    class_version = '20071216'
    class_title = MSG(u"RTF")
    class_description = MSG(u'RTF Document')
    class_icon16 = 'icons/16x16/text.png'
    class_icon48 = 'icons/48x48/text.png'
    class_handler = RTFFile



class ODT(File):
    class_id = 'application/vnd.oasis.opendocument.text'
    class_version = '20071216'
    class_title = MSG(u'ODT')
    class_description = MSG(u'OpenDocument Text')
    class_icon16 = 'icons/16x16/odt.png'
    class_icon48 = 'icons/48x48/odt.png'
    class_handler = ODTFile



class ODS(File):
    class_id = 'application/vnd.oasis.opendocument.spreadsheet'
    class_version = '20071216'
    class_title = MSG(u'ODS')
    class_description = MSG(u'OpenDocument Spreadsheet')
    class_icon16 = 'icons/16x16/ods.png'
    class_icon48 = 'icons/48x48/ods.png'
    class_handler = ODSFile



class ODP(File):
    class_id = 'application/vnd.oasis.opendocument.presentation'
    class_version = '20071216'
    class_title = MSG(u'ODP')
    class_description = MSG(u'OpenDocument Presentation')
    class_icon16 = 'icons/16x16/odp.png'
    class_icon48 = 'icons/48x48/odp.png'
    class_handler = ODPFile



###########################################################################
# Archive Files
###########################################################################
class Archive(File):

    view = Archive_View()



class ZipArchive(Archive):
    class_id = 'application/zip'
    class_version = '20071216'
    class_title = MSG(u"Zip")
    class_description = MSG(u'Zip Archive')
    class_icon16 = 'icons/16x16/zip.png'
    class_icon48 = 'icons/48x48/zip.png'
    class_handler = ZIPFile



class TarArchive(Archive):
    class_id = 'application/x-tar'
    class_version = '20071216'
    class_title = MSG(u"Tar")
    class_description = MSG(u'Tar Archive')
    class_icon16 = 'icons/16x16/tar.png'
    class_icon48 = 'icons/48x48/tar.png'
    class_handler = TARFile



class Gzip(File):
    class_id = 'application/x-gzip'
    class_version = '20071216'
    class_title = MSG(u"Gzip")
    class_description = MSG(u'Gzip Compressed')
    class_icon16 = 'icons/16x16/gzip.png'
    class_icon48 = 'icons/48x48/gzip.png'
    class_handler = GzipFile



class Bzip2(File):
    class_id = 'application/x-bzip2'
    class_version = '20071216'
    class_title = MSG(u"Bzip2")
    class_description = MSG(u'Bzip2 Compressed')
    class_icon16 = 'icons/16x16/bzip.png'
    class_icon48 = 'icons/48x48/bzip.png'
    class_handler = Bzip2File


###########################################################################
# Register
###########################################################################
register_resource_class(File)
register_resource_class(File, format="application/octet-stream")
# Media
for cls in Image, Video, Flash:
    register_resource_class(cls)
# Office
for cls in MSWord, MSExcel, MSPowerPoint, PDF, RTF:
    register_resource_class(cls)
# OpenOffice 1.0 & ODF
for cls in OOWriter, OOCalc, OOImpress, ODT, ODS, ODP:
    register_resource_class(cls)
# Archives
for cls in ZipArchive, TarArchive, Gzip, Bzip2:
    register_resource_class(cls)

