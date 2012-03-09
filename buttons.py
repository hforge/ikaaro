# -*- coding: UTF-8 -*-
# Copyright (C) 2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from itools.core import proto_property, proto_lazy_property
from itools.gettext import MSG
from itools.stl import STLTemplate

# Import from ikaaro
from datatypes import CopyCookie
from utils import make_stl_template


class Button(STLTemplate):
    access = False
    template = make_stl_template('''
        <button type="submit" id="${id}" name="${action}" value="${name}"
            class="${css}" onclick="${onclick}">${title}</button>''')
    id = None
    # TODO rename to "value" in 0.75
    name = None
    # TODO rename to "content" in 0.75, add "title" attribute
    title = MSG(u"OK")
    css = 'button-ok'
    confirm = None


    # TODO rename to "name" in 0.75
    @proto_property
    def action(cls):
        if cls.name is None:
            return None
        return 'action'


    @proto_property
    def onclick(cls):
        confirm = cls.confirm
        if not confirm:
            return None
        return u'return confirm("%s");' % confirm.gettext()


    @proto_lazy_property
    def show(self):
        context = self.context
        return context.is_access_allowed(context.resource, self)


###########################################################################
# Buttons that apply to one item
###########################################################################
class Remove_Button(Button):

    access = 'is_allowed_to_remove'
    confirm = MSG(u'Are you sure you want to delete this?')
    css = 'button-delete'
    name = 'remove'
    title = MSG(u'Remove')


###########################################################################
# Buttons that apply to several items
###########################################################################
class BrowseButton(Button):

    @proto_lazy_property
    def show(self):
        context = self.context
        for item in self.items:
            if context.is_access_allowed(item, self):
                return True
        return False



class Remove_BrowseButton(Remove_Button, BrowseButton):

    confirm = MSG(u'Are you sure you want to delete the selection?')



class RenameButton(BrowseButton):

    access = 'is_allowed_to_move'
    css = 'button-rename'
    name = 'rename'
    title = MSG(u'Rename')



class CopyButton(BrowseButton):

    access = 'is_allowed_to_copy'
    css = 'button-copy'
    name = 'copy'
    title = MSG(u'Copy')



class CutButton(BrowseButton):

    access = 'is_allowed_to_move'
    css = 'button-cut'
    name = 'cut'
    title = MSG(u'Cut')



class PasteButton(BrowseButton):

    access = 'is_allowed_to_move'
    css = 'button-paste'
    name = 'paste'
    title = MSG(u'Paste')


    @proto_lazy_property
    def show(cls):
        cut, paths = cls.context.get_cookie('ikaaro_cp', datatype=CopyCookie)
        if len(paths) == 0:
            return False
        return super(BrowseButton, cls).show



class AddButton(BrowseButton):

    access = 'is_allowed_to_edit'
    name = 'add'
    title = MSG(u'Add')
    css = 'button-add'



class ZipButton(BrowseButton):

    access = 'is_allowed_to_edit'
    name = 'zip'
    title = MSG(u'Zip')
    css = 'button-zip'
