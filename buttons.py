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
from itools.gettext import MSG

# Import from ikaaro
from datatypes import CopyCookie
import messages


class Button(object):

    access = False
    confirm = None
    css = 'button_ok'
    name = None
    title = None

    def __init__(self, **kw):
        for key in kw:
            setattr(self, key, kw[key])


    @classmethod
    def show(cls, resource, context, items):
        if len(items) == 0:
            return False
        ac = resource.get_access_control()
        return ac.is_access_allowed(context.user, resource, cls)



class RemoveButton(Button):

    access = 'is_allowed_to_remove'
    confirm = messages.MSG_DELETE_SELECTION
    css = 'button_delete'
    name = 'remove'
    title = MSG(u'Remove')



class RenameButton(Button):

    access = 'is_allowed_to_move'
    css = 'button_rename'
    name = 'rename'
    title = MSG(u'Rename')



class CopyButton(Button):

    access = 'is_allowed_to_copy'
    css = 'button_copy'
    name = 'copy'
    title = MSG(u'Copy')



class CutButton(Button):

    access = 'is_allowed_to_move'
    css = 'button_cut'
    name = 'cut'
    title = MSG(u'Cut')



class PasteButton(Button):

    access = 'is_allowed_to_move'
    css = 'button_paste'
    name = 'paste'
    title = MSG(u'Paste')


    @classmethod
    def show(cls, resource, context, items):
        cut, paths = context.get_cookie('ikaaro_cp', type=CopyCookie)
        if len(paths) == 0:
            return False
        ac = resource.get_access_control()
        return ac.is_access_allowed(context.user, resource, cls)



class PublishButton(Button):

    access = 'is_allowed_to_publish'
    css = 'button_publish'
    name = 'publish'
    title = MSG(u'Publish')


    @classmethod
    def show(cls, resource, context, items):
        ac = resource.get_access_control()
        for item in items:
            if ac.is_allowed_to_trans(context.user, item, 'publish'):
                return True
        return False



class OrderUpButton(Button):

    access = 'is_allowed_to_edit'
    name = 'order_up'
    title = MSG(u'Order up')



class OrderDownButton(Button):

    access = 'is_allowed_to_edit'
    name = 'order_down'
    title = MSG(u'Order down')



class OrderTopButton(Button):

    access = 'is_allowed_to_edit'
    name = 'order_top'
    title = MSG(u'Order top')



class OrderBottomButton(Button):

    access = 'is_allowed_to_edit'
    name = 'order_bottom'
    title = MSG(u'Order bottom')

