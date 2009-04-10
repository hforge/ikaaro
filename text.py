# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from itools.csv import CSVFile
from itools.gettext import POFile, MSG
from itools.handlers import TextFile, Python as PythonFile
from itools.html import HTMLFile
from itools.utils import add_type
from itools.xml import XMLFile

# Import from ikaaro
from file import File
from file_views import File_Upload
from registry import register_resource_class
from text_views import Text_Edit, Text_View, Text_ExternalEdit, PO_Edit
from text_views import CSV_View, CSV_AddRow, CSV_EditRow



class Text(File):

    class_id = 'text'
    class_version = '20071216'
    class_title = MSG(u'Plain Text')
    class_icon16 = 'icons/16x16/text.png'
    class_icon48 = 'icons/48x48/text.png'
    class_views = ['view', 'edit', 'externaledit', 'upload',
                   'edit_state', 'history']
    class_handler = TextFile


    def get_content_type(self):
        return '%s; charset=UTF-8' % File.get_content_type(self)


    # Views
    view = Text_View()
    edit = Text_Edit()
    upload = File_Upload()
    externaledit = Text_ExternalEdit()



class PO(Text):

    class_id = 'text/x-gettext-translation'
    class_version = '20071216'
    class_title = MSG(u'Message Catalog')
    class_icon16 = 'icons/16x16/po.png'
    class_icon48 = 'icons/48x48/po.png'
    class_handler = POFile

    # Views
    edit = PO_Edit()



class CSS(Text):

    class_id = 'text/css'
    class_version = '20071216'
    class_title = MSG(u'CSS')
    class_icon16 = 'icons/16x16/css.png'
    class_icon48 = 'icons/48x48/css.png'



class Python(Text):

    class_id = 'text/x-python'
    class_version = '20071216'
    class_title = MSG(u'Python')
    class_icon16 = 'icons/16x16/python.png'
    class_icon48 = 'icons/48x48/python.png'
    class_handler = PythonFile



class JS(Text):

    class_id = 'application/x-javascript'
    class_version = '20071216'
    class_title = MSG(u'Javascript')
    class_icon16 = 'icons/16x16/js.png'
    class_icon48 = 'icons/48x48/js.png'



class XML(Text):

    class_id = 'text/xml'
    class_version = '20071216'
    class_title = MSG(u'XML File')
    class_handler = XMLFile



class HTML(Text):

    class_id = 'text/html'
    class_version = '20071216'
    class_title = MSG(u'HTML File')
    class_handler = HTMLFile



class CSV(Text):

    class_id = 'text/comma-separated-values'
    class_version = '20071216'
    class_title = MSG(u'Comma Separated Values')
    class_views = ['view', 'add_row', 'edit', 'externaledit', 'upload',
                   'history']
    class_handler = CSVFile


    def get_columns(self):
        """Returns a list of tuples with the name and title of every column.
        """
        handler = self.handler

        if handler.columns is None:
            row = None
            for row in handler.lines:
                if row is not None:
                    break
            if row is None:
                return []
            return [ (str(x), str(x)) for x in range(len(row)) ]

        columns = []
        for name in handler.columns:
            datatype = handler.schema[name]
            title = getattr(datatype, 'title', None)
            if title is None:
                title = name
            else:
                title = title.gettext()
            columns.append((name, title))

        return columns


    # Views
    edit = None
    view = CSV_View()
    add_row = CSV_AddRow()
    edit_row = CSV_EditRow()



###########################################################################
# Register
###########################################################################
register_resource_class(Text)
register_resource_class(Python)
for js_mime in ['application/x-javascript', 'text/javascript',
                'application/javascript']:
    register_resource_class(JS, js_mime)
    add_type(js_mime, '.js')
register_resource_class(PO)
register_resource_class(CSS)
register_resource_class(XML)
register_resource_class(XML, format='application/xml')
register_resource_class(HTML)
register_resource_class(CSV)
register_resource_class(CSV, 'text/x-comma-separated-values')
register_resource_class(CSV, 'text/csv')

