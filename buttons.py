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
    def hide(cls, items, context):
        return len(items) == 0



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
    def hide(cls, items, context):
        cut, paths = context.get_cookie('ikaaro_cp', type=CopyCookie)
        return len(paths) == 0



class PublishButton(Button):

    access = 'is_allowed_to_publish'
    css = 'button_publish'
    name = 'publish'
    title = MSG(u'Publish')

