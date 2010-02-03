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
from itools.web import make_stl_template

# Import from ikaaro
from datatypes import CopyCookie
import messages
from utils import CMSTemplate


class Button(CMSTemplate):

    access = False
    confirm = None
    css = 'button-ok'
    name = None
    title = None

    template = make_stl_template("""
        <button type="submit" name="action" value="${name}" class="${css}"
          onclick="${onclick}">${title}</button>""")


    def onclick(self):
        if self.confirm:
            confirm = self.confirm.gettext().encode('utf-8')
            return 'return confirm("%s");' % confirm
        return None


    def show(self, resource, context, items):
        if len(items) == 0:
            return False
        ac = resource.access_control
        return ac.is_access_allowed(context, resource, self)



class RemoveButton(Button):

    access = 'is_allowed_to_remove'
    confirm = messages.MSG_DELETE_SELECTION
    css = 'button-delete'
    name = 'remove'
    title = MSG(u'Remove')



class RenameButton(Button):

    access = 'is_allowed_to_move'
    css = 'button-rename'
    name = 'rename'
    title = MSG(u'Rename')



class CopyButton(Button):

    access = 'is_allowed_to_copy'
    css = 'button-copy'
    name = 'copy'
    title = MSG(u'Copy')



class CutButton(Button):

    access = 'is_allowed_to_move'
    css = 'button-cut'
    name = 'cut'
    title = MSG(u'Cut')



class PasteButton(Button):

    access = 'is_allowed_to_move'
    css = 'button-paste'
    name = 'paste'
    title = MSG(u'Paste')


    def show(self, resource, context, items):
        cut, paths = context.get_cookie('ikaaro_cp', datatype=CopyCookie)
        if len(paths) == 0:
            return False
        ac = resource.access_control
        return ac.is_access_allowed(context, resource, self)



class PublishButton(Button):

    access = 'is_allowed_to_publish'
    css = 'button-publish'
    name = 'publish'
    title = MSG(u'Publish')


    def show(self, resource, context, items):
        ac = resource.access_control
        for item in items:
            if ac.is_allowed_to_trans(context.user, item, 'publish'):
                return True
        return False



class RetireButton(Button):

    access = 'is_allowed_to_retire'
    css = 'button-retire'
    name = 'retire'
    title = MSG(u'Unpublish')


    def show(self, resource, context, items):
        ac = resource.access_control
        for item in items:
            if type(item) is tuple:
                item = item[1]
            if ac.is_allowed_to_trans(context.user, item, 'retire'):
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

