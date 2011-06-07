# -*- coding: UTF-8 -*-
# Copyright (C) 2011 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from itools.core import merge_dicts
from itools.datatypes import DateTime, Unicode
from itools.gettext import MSG
from itools.web import get_context

# Import from ikaaro
from autoform import TextWidget, timestamp_widget
from config import Configuration
from resource_ import DBResource
from resource_views import DBResource_Edit
from utils import make_stl_template


class CaptchaDatatype(Unicode):
    mandatory = True


    @staticmethod
    def is_valid(value):
        website = get_context().site_root
        captcha = website.get_resource('config/captcha')
        return captcha.get_property('captcha_answer') == value



class CaptchaWidget(TextWidget):
    title = MSG(u"Please answer the question below:")
    template = make_stl_template("""
    ${question}
    <input type="text" id="${id}" name="${name}" value="${value}"
      maxlength="${maxlength}" size="${size}" />""")


    def question(self):
        website = get_context().site_root
        captcha = website.get_resource('config/captcha')
        return captcha.get_property('captcha_question')



###########################################################################
# Resource & View
###########################################################################
class Captcha_Edit(DBResource_Edit):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit captcha')

    schema = {
        'timestamp': DateTime(readonly=True),
        'captcha_question': Unicode(mandatory=True),
        'captcha_answer': Unicode(mandatory=True)}

    widgets = [
        timestamp_widget,
        TextWidget('captcha_question', title=MSG(u"Captcha question")),
        TextWidget('captcha_answer', title=MSG(u"Captcha answer"))]



class Captcha(DBResource):
    
    class_id = 'config-captcha'
    class_version = '20110606'
    class_title = MSG(u'Captcha')
    class_description = MSG(u'...')
    class_icon48 = 'icons/48x48/captcha.png'
    class_views = ['edit']

    class_schema = merge_dicts(
        DBResource.class_schema,
        captcha_question=Unicode(source='metadata', default=u"2 + 3"),
        captcha_answer=Unicode(source='metadata', default=u"5"))

    edit = Captcha_Edit()


Configuration.register_plugin('captcha', Captcha)
