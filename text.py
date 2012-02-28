# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2008 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2011 Armel FORTUN <armel@tchack.com>
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
from re import compile

# Import from itools
from itools.core import add_type
from itools.csv import CSVFile
from itools.gettext import POFile, MSG
from itools.handlers import TextFile
from itools.html import HTMLFile
from itools.python import Python as PythonFile
from itools.uri import get_reference, Path, Reference
from itools.web import get_context
from itools.xmlfile import XMLFile

# Import from ikaaro
from autoform import MultilineWidget
from database import Database
from file import File
from file_views import File_Edit
from text_views import Text_Edit, Text_View, PO_Edit
from text_views import CSV_View, CSV_AddRow, CSV_EditRow
from text_views import CSS_Edit

css_uri_expr = compile(r"url\((.*)\)")
def css_get_reference(uri):
    # FIXME Not compliant with
    # http://www.w3.org/TR/CSS2/syndata.html#value-def-uri
    value = uri.strip()
    # remove optional " or '
    if value and value[0] in ("'", '"'):
        value = value[1:]
    # remove optional " or '
    if value and value[-1] in ("'", '"'):
        value = value[:-1]

    return get_reference(value)



class Text(File):

    class_id = 'text'
    class_title = MSG(u'Plain Text')
    class_icon16 = 'icons/16x16/text.png'
    class_icon48 = 'icons/48x48/text.png'
    class_views = ['view', 'edit', 'externaledit', 'commit_log']
    # Fields
    data = File.data(class_handler=TextFile, widget=MultilineWidget)


    def get_content_type(self):
        return '%s; charset=UTF-8' % super(Text, self).get_content_type()


    # Views
    view = Text_View
    edit = Text_Edit



class PO(Text):

    class_id = 'text/x-gettext-translation'
    class_title = MSG(u'Message Catalog')
    class_icon16 = 'icons/16x16/po.png'
    class_icon48 = 'icons/48x48/po.png'
    # Fields
    data = Text.data(class_handler=POFile)

    # Views
    edit = PO_Edit



class CSS(Text):

    class_id = 'text/css'
    class_title = MSG(u'CSS')
    class_icon16 = 'icons/16x16/css.png'
    class_icon48 = 'icons/48x48/css.png'


    def get_links(self):
        links = super(CSS, self).get_links()
        base = self.abspath
        data = self.to_text().encode('utf-8')

        segments = css_uri_expr.findall(data)
        for segment in segments:
            reference = css_get_reference(segment)

            # Skip empty links, external links and links to '/ui/'
            if reference.scheme or reference.authority:
                continue
            path = reference.path
            if not path or path[0] == 'ui':
                continue

            # Strip the view
            name = path.get_name()
            if name and name[0] == ';':
                path = path[:-1]

            # Absolute path are relative to site root
            if not path.is_absolute():
                uri = base.resolve2(path)

            links.add(str(uri))

        return links


    def update_links(self,  source, target):
        super(CSS, self).update_links(source, target)
        resources_new2old = get_context().database.resources_new2old
        base = str(self.abspath)
        old_base = resources_new2old.get(base, base)
        old_base = Path(old_base)
        new_base = Path(base)

        def my_func(matchobj):
            uri = matchobj.group(1)
            reference = css_get_reference(uri)

            # Skip empty links, external links and links to '/ui/'
            if reference.scheme or reference.authority:
                return matchobj.group(0)
            path = reference.path
            if not path or path[0] == 'ui':
                return matchobj.group(0)

            # Strip the view
            name = path.get_name()
            if name and name[0] == ';':
                view = '/' + name
                path = path[:-1]
            else:
                view = ''

            # Resolve the path
            # Absolute path are relative to site root
            if not path.is_absolute():
                path = old_base.resolve2(path)

            # Match ?
            if path == source:
                path = str(new_base.get_pathto(target)) + view
                new_path = Reference('', '', path, reference.query.copy(),
                                     reference.fragment)
                return "url('%s')" % new_path

            return matchobj.group(0)

        data = self.to_text().encode('utf-8')
        new_data = css_uri_expr.sub(my_func, data)
        self.handler.load_state_from_string(new_data)

        get_context().database.change_resource(self)


    def update_incoming_links(self, source):
        super(CSS, self).update_incoming_links(source)
        target = self.abspath
        resources_old2new = get_context().database.resources_old2new

        def my_func(matchobj):
            uri = matchobj.group(1)
            reference = css_get_reference(uri)

            # Skip empty links, external links and links to '/ui/'
            if reference.scheme or reference.authority:
                return matchobj.group(0)
            path = reference.path
            if not path or path[0] == 'ui':
                return matchobj.group(0)

            # Strip the view
            name = path.get_name()
            if name and name[0] == ';':
                view = '/' + name
                path = path[:-1]
            else:
                view = ''

            # Calcul the old absolute path
            # Absolute path are relative to site root
            if not path.is_absolute():
                old_abs_path = source.resolve2(path)
            # Get the 'new' absolute parth
            new_abs_path = resources_old2new.get(old_abs_path, old_abs_path)

            path = str(target.get_pathto(new_abs_path)) + view
            new_value = Reference('', '', path, reference.query.copy(),
                                  reference.fragment)
            return "url('%s')" % path

        data = self.to_text().encode('utf-8')
        new_data = css_uri_expr.sub(my_func, data)
        self.handler.load_state_from_string(new_data)


    # Views
    edit = CSS_Edit



class Python(Text):

    class_id = 'text/x-python'
    class_title = MSG(u'Python')
    class_icon16 = 'icons/16x16/python.png'
    class_icon48 = 'icons/48x48/python.png'
    # Fields
    data = Text.data(class_handler=PythonFile)



class JS(Text):

    class_id = 'application/x-javascript'
    class_title = MSG(u'Javascript')
    class_icon16 = 'icons/16x16/js.png'
    class_icon48 = 'icons/48x48/js.png'



class XML(Text):

    class_id = 'text/xml'
    class_title = MSG(u'XML File')
    # Fields
    data = Text.data(class_handler=XMLFile)



class HTML(Text):

    class_id = 'text/html'
    class_title = MSG(u'HTML File')
    # Fields
    data = Text.data(class_handler=HTMLFile)



class CSV(Text):

    class_id = 'text/comma-separated-values'
    class_title = MSG(u'Comma Separated Values')
    class_views = ['view', 'add_row', 'edit', 'externaledit', 'commit_log']
    # Fields
    data = Text.data(class_handler=CSVFile)


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
    edit = File_Edit
    view = CSV_View
    add_row = CSV_AddRow
    edit_row = CSV_EditRow



###########################################################################
# Register
###########################################################################
for js_mime in ['application/x-javascript', 'text/javascript',
                'application/javascript']:
    Database.register_resource_class(JS, js_mime)
    add_type(js_mime, '.js')

Database.register_resource_class(XML, 'application/xml')
Database.register_resource_class(CSV, 'text/x-comma-separated-values')
Database.register_resource_class(CSV, 'text/csv')
