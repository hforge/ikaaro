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
from itools.gettext import POFile, MSG
from itools.handlers import TextFile, Python as PythonFile
from itools.html import HTMLFile
from itools.stl import stl
from itools.xml import XMLFile

# Import from ikaaro
from file import File
from registry import register_object_class
from text_views import TextEdit, TextView, TextExternalEdit, POEdit



class Text(File):

    class_id = 'text'
    class_version = '20071216'
    class_title = MSG(u'Plain Text')
    class_icon16 = 'icons/16x16/text.png'
    class_icon48 = 'icons/48x48/text.png'
    class_views = ['view', 'edit', 'externaledit', 'upload', 'edit_metadata',
                   'edit_state', 'history']
    class_handler = TextFile


    def get_content_type(self):
        return '%s; charset=UTF-8' % File.get_content_type(self)


    # Views
    edit = TextEdit()
    view = TextView()
    externaledit = TextExternalEdit()



class PO(Text):

    class_id = 'text/x-gettext-translation'
    class_version = '20071216'
    class_title = MSG(u'Message Catalog')
    class_icon16 = 'icons/16x16/po.png'
    class_icon48 = 'icons/48x48/po.png'
    class_handler = POFile

    # Views
    edit = POEdit()



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



###########################################################################
# Register
###########################################################################
register_object_class(Text)
register_object_class(Python)
register_object_class(PO)
register_object_class(CSS)
register_object_class(XML)
register_object_class(XML, format='application/xml')
register_object_class(HTML)

