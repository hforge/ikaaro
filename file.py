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

# Import from itools
from itools.core import guess_all_extensions
from itools.gettext import MSG
from itools.handlers import File as FileHandler
from itools.handlers import Image as ImageHandler, SVGFile
from itools.handlers import TARFile, ZIPFile, GzipFile, Bzip2File
from itools.odf import SXWFile, SXCFile, SXIFile, ODTFile, ODSFile, ODPFile
from itools.pdf import PDFFile
from itools.office import RTF as RTFFile
from itools.office import MSWord as MSWordFile, MSExcel as MSExcelFile
from itools.office import MSPowerPoint as MSPowerPointFile
from itools.office import MSWordX as MSWordXFile, MSExcelX as MSExcelXFile
from itools.office import MSPowerPointX as MSPowerPointXFile
from itools.web import get_context

# Import from ikaaro
from content import Content
from database import Database
from fields import Char_Field, File_Field, Owner_Field
from file_views import File_NewInstance, File_View
from file_views import File_Edit, File_ExternalEdit, File_ExternalEdit_View
from file_views import File_Download
from file_views import Image_View, Video_View, Archive_View
from file_views import Flash_View
from resource_views import DBResource_GetImage



###########################################################################
# Base File
###########################################################################
class File(Content):

    class_id = 'file'
    class_version = '20090122'
    class_title = MSG(u'File')
    class_description = MSG(
        u'Upload office documents, images, media files, etc.')
    class_icon16 = 'icons/16x16/file.png'
    class_icon48 = 'icons/48x48/file.png'
    class_views = ['view', 'edit', 'externaledit', 'remove', 'subscribe',
                   'links', 'backlinks', 'commit_log']

    # Fields
    data = File_Field(required=True, class_handler=FileHandler)
    filename = Char_Field
    owner = Owner_Field


    def get_all_extensions(self):
        format = self.metadata.format
        # FIXME This is a hack, compression encodings are not yet properly
        # supported (to do for the next major version).
        if format == 'application/x-gzip':
            extensions = ['gz', 'tgz']
        elif format == 'application/x-bzip2':
            extensions = ['bz2', 'tbz2']
        else:
            cls = self.data.class_handler
            extensions = [ x[1:] for x in guess_all_extensions(format) ]
            if cls.class_extension in extensions:
                extensions.remove(cls.class_extension)
            extensions.insert(0, cls.class_extension)
        return extensions


    #######################################################################
    # Versioning & Indexing
    #######################################################################
    def to_text(self):
        return self.get_value('data').to_text()


    def get_files_to_archive(self, content=False):
        # Handlers
        files = [ x.key for x in self.get_handlers() ]
        # Metadata
        metadata = self.metadata.key
        files.append(metadata)
        return files


    #######################################################################
    # User Interface
    #######################################################################
    def get_content_type(self):
        return self.get_value('data').get_mimetype()

    # Views
    new_instance = File_NewInstance
    download = File_Download
    view = File_View
    edit = File_Edit
    externaledit = File_ExternalEdit_View
    external_edit = File_ExternalEdit



###########################################################################
# Media
###########################################################################
class Image(File):

    class_id = 'image'
    class_title = MSG(u'Image')
    class_icon16 = 'icons/16x16/image.png'
    class_icon48 = 'icons/48x48/image.png'
    class_views = ['view', 'download', 'edit', 'externaledit', 'remove',
                   'links', 'backlinks', 'commit_log']
    # Fields
    data = File.data(class_handler=ImageHandler)

    def get_max_width(self):
        # Auto-reduce width on init
        server = get_context().server
        if server is not None:
            return server.config.get_value('max-width')
        return None


    def get_max_height(self):
        # Auto-reduce height on init
        server = get_context().server
        if server is not None:
            return server.config.get_value('max-height')
        return None


    def init_resource(self, **kw):
        super(Image, self).init_resource(**kw)
        # Resize image at max size
        max_width = self.get_max_width()
        max_height = self.get_max_height()
        if max_width or max_height:
            handler = self.get_value('data')
            xsize, ysize = handler.get_size()
            thumb, format = handler.get_thumbnail(
                min(xsize, max_width or xsize),
                min(ysize, max_height or ysize))
            handler.load_state_from_string(thumb)

    # Views
    thumb = DBResource_GetImage(field_name='data')
    view = Image_View



class SVG(Image):
    class_id = 'image/svg+xml'
    class_title = MSG(u'Image SVG')
    # Fields
    data = Image.data(class_handler=SVGFile)



class Video(File):
    class_id = 'video'
    class_title = MSG(u'Video')
    class_description = MSG(u'Video')
    class_icon16 = 'icons/16x16/flash.png'
    class_icon48 = 'icons/48x48/flash.png'

    # Views
    view = Video_View



class Flash(File):
    class_id = 'application/x-shockwave-flash'
    class_title = MSG(u'Flash')
    class_description = MSG(u'Flash Document')
    class_icon16 = 'icons/16x16/flash.png'
    class_icon48 = 'icons/48x48/flash.png'

    # Views
    view = Flash_View



###########################################################################
# Office Documents
###########################################################################
class MSWord(File):
    class_id = 'application/msword'
    class_title = MSG(u'Word')
    class_description = MSG(u'Word Text')
    class_icon16 = 'icons/16x16/word.png'
    class_icon48 = 'icons/48x48/word.png'
    # Fields
    data = File.data(class_handler=MSWordFile)



class MSExcel(File):
    class_id = 'application/vnd.ms-excel'
    class_title = MSG(u'Excel')
    class_description = MSG(u'Excel Spreadsheet')
    class_icon16 = 'icons/16x16/excel.png'
    class_icon48 = 'icons/48x48/excel.png'
    # Fields
    data = File.data(class_handler=MSExcelFile)



class MSPowerPoint(File):
    class_id = 'application/vnd.ms-powerpoint'
    class_title = MSG(u'PowerPoint')
    class_description = MSG(u'PowerPoint Presentation')
    class_icon16 = 'icons/16x16/powerpoint.png'
    class_icon48 = 'icons/48x48/powerpoint.png'
    # Fields
    data = File.data(class_handler=MSPowerPointFile)



class MSWordX(File):
    class_id = MSWordXFile.class_mimetypes[0]
    class_title = MSG(u'Word')
    class_description = MSG(u'Word Text')
    class_icon16 = 'icons/16x16/word.png'
    class_icon48 = 'icons/48x48/word.png'
    # Fields
    data = File.data(class_handler=MSWordXFile)



class MSExcelX(File):
    class_id = MSExcelXFile.class_mimetypes[0]
    class_title = MSG(u'Excel')
    class_description = MSG(u'Excel Spreadsheet')
    class_icon16 = 'icons/16x16/excel.png'
    class_icon48 = 'icons/48x48/excel.png'
    # Fields
    data = File.data(class_handler=MSExcelXFile)



class MSPowerPointX(File):
    class_id = MSPowerPointXFile.class_mimetypes[0]
    class_title = MSG(u'PowerPoint')
    class_description = MSG(u'PowerPoint Presentation')
    class_icon16 = 'icons/16x16/powerpoint.png'
    class_icon48 = 'icons/48x48/powerpoint.png'
    # Fields
    data = File.data(class_handler=MSPowerPointXFile)



class OOWriter(File):
    class_id = 'application/vnd.sun.xml.writer'
    class_title = MSG(u'OOo Writer')
    class_description = MSG(u'OpenOffice.org Text')
    class_icon16 = 'icons/16x16/oowriter.png'
    class_icon48 = 'icons/48x48/oowriter.png'
    # Fields
    data = File.data(class_handler=SXWFile)



class OOCalc(File):
    class_id = 'application/vnd.sun.xml.calc'
    class_title = MSG(u'OOo Calc')
    class_description = MSG(u'OpenOffice.org Spreadsheet')
    class_icon16 = 'icons/16x16/oocalc.png'
    class_icon48 = 'icons/48x48/oocalc.png'
    # Fields
    data = File.data(class_handler=SXCFile)



class OOImpress(File):
    class_id = 'application/vnd.sun.xml.impress'
    class_title = MSG(u'OOo Impress')
    class_description = MSG(u'OpenOffice.org Presentation')
    class_icon16 = 'icons/16x16/ooimpress.png'
    class_icon48 = 'icons/48x48/ooimpress.png'
    # Fields
    data = File.data(class_handler=SXIFile)



class PDF(File):
    class_id = 'application/pdf'
    class_title = MSG(u'PDF')
    class_description = MSG(u'PDF Document')
    class_icon16 = 'icons/16x16/pdf.png'
    class_icon48 = 'icons/48x48/pdf.png'
    # Fields
    data = File.data(class_handler=PDFFile)



class RTF(File):
    class_id = 'text/rtf'
    class_title = MSG(u"RTF")
    class_description = MSG(u'RTF Document')
    class_icon16 = 'icons/16x16/text.png'
    class_icon48 = 'icons/48x48/text.png'
    # Fields
    data = File.data(class_handler=RTFFile)



class ODT(File):
    class_id = 'application/vnd.oasis.opendocument.text'
    class_title = MSG(u'ODT')
    class_description = MSG(u'OpenDocument Text')
    class_icon16 = 'icons/16x16/odt.png'
    class_icon48 = 'icons/48x48/odt.png'
    # Fields
    data = File.data(class_handler=ODTFile)



class ODS(File):
    class_id = 'application/vnd.oasis.opendocument.spreadsheet'
    class_title = MSG(u'ODS')
    class_description = MSG(u'OpenDocument Spreadsheet')
    class_icon16 = 'icons/16x16/ods.png'
    class_icon48 = 'icons/48x48/ods.png'
    # Fields
    data = File.data(class_handler=ODSFile)



class ODP(File):
    class_id = 'application/vnd.oasis.opendocument.presentation'
    class_title = MSG(u'ODP')
    class_description = MSG(u'OpenDocument Presentation')
    class_icon16 = 'icons/16x16/odp.png'
    class_icon48 = 'icons/48x48/odp.png'
    # Fields
    data = File.data(class_handler=ODPFile)



###########################################################################
# Archive Files
###########################################################################
class Archive(File):

    view = Archive_View



class ZipArchive(Archive):
    class_id = 'application/zip'
    class_title = MSG(u"Zip")
    class_description = MSG(u'Zip Archive')
    class_icon16 = 'icons/16x16/zip.png'
    class_icon48 = 'icons/48x48/zip.png'
    # Fields
    data = Archive.data(class_handler=ZIPFile)



class TarArchive(Archive):
    class_id = 'application/x-tar'
    class_title = MSG(u"Tar")
    class_description = MSG(u'Tar Archive')
    class_icon16 = 'icons/16x16/tar.png'
    class_icon48 = 'icons/48x48/tar.png'
    # Fields
    data = Archive.data(class_handler=TARFile)



class Gzip(File):
    class_id = 'application/x-gzip'
    class_title = MSG(u"Gzip")
    class_description = MSG(u'Gzip Compressed')
    class_icon16 = 'icons/16x16/gzip.png'
    class_icon48 = 'icons/48x48/gzip.png'
    # Fields
    data = File.data(class_handler=GzipFile)



class Bzip2(File):
    class_id = 'application/x-bzip2'
    class_title = MSG(u"Bzip2")
    class_description = MSG(u'Bzip2 Compressed')
    class_icon16 = 'icons/16x16/bzip.png'
    class_icon48 = 'icons/48x48/bzip.png'
    # Fields
    data = File.data(class_handler=Bzip2File)


###########################################################################
# Register
###########################################################################
Database.register_resource_class(File, 'application/octet-stream')
Database.register_resource_class(ZipArchive, 'application/x-zip-compressed')
