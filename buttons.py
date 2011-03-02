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
from itools.core import thingy_property
from itools.gettext import MSG
from itools.stl import STLTemplate

# Import from ikaaro
from datatypes import CopyCookie
import messages
from utils import make_stl_template


class Button(STLTemplate):
    access = False
    template = make_stl_template('''
        <button type="submit" name="${action}" value="${name}" class="${css}"
            onclick="${onclick}">${title}</button>''')
    name = None
    title = None
    css = 'button-ok'
    confirm = None


    @thingy_property
    def action(cls):
        if cls.name is None:
            return None
        return 'action'


    @thingy_property
    def onclick(cls):
        confirm = cls.confirm
        if not confirm:
            return None
        return u'return confirm("%s");' % confirm.gettext()


    @thingy_property
    def show(cls):
        ac = cls.resource.get_access_control()
        return ac.is_access_allowed(cls.context.user, cls.resource, cls)



class BrowseButton(Button):

    @thingy_property
    def show(cls):
        if len(cls.items) == 0:
            return False
        return super(BrowseButton, cls).show



class RemoveButton(BrowseButton):

    access = 'is_allowed_to_remove'
    confirm = messages.MSG_DELETE_SELECTION
    css = 'button-delete'
    name = 'remove'
    title = MSG(u'Remove')



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


    @thingy_property
    def show(cls):
        cut, paths = cls.context.get_cookie('ikaaro_cp', datatype=CopyCookie)
        if len(paths) == 0:
            return False
        return super(PasteButton, cls).show



class PublishButton(BrowseButton):

    access = 'is_allowed_to_publish'
    css = 'button-publish'
    name = 'publish'
    title = MSG(u'Publish')
    transition = 'publish'


    @thingy_property
    def show(cls):
        ac = cls.resource.get_access_control()
        for item in cls.items:
            if type(item) is tuple:
                item = item[1]
            if ac.is_allowed_to_trans(cls.context.user, item, cls.transition):
                return True
        return False



class RetireButton(PublishButton):

    access = 'is_allowed_to_retire'
    css = 'button-retire'
    name = 'retire'
    title = MSG(u'Unpublish')
    transition = 'retire'



class OrderUpButton(BrowseButton):

    access = 'is_allowed_to_edit'
    name = 'order_up'
    title = MSG(u'Order up')



class OrderDownButton(BrowseButton):

    access = 'is_allowed_to_edit'
    name = 'order_down'
    title = MSG(u'Order down')



class OrderTopButton(BrowseButton):

    access = 'is_allowed_to_edit'
    name = 'order_top'
    title = MSG(u'Order top')



class OrderBottomButton(BrowseButton):

    access = 'is_allowed_to_edit'
    name = 'order_bottom'
    title = MSG(u'Order bottom')



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
