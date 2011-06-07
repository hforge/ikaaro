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
from itools.datatypes import Unicode
from itools.gettext import MSG
from itools.web import get_context

# Import from ikaaro
from autoedit import AutoEdit
from autoform import TextWidget
from config import Configuration
from resource_ import DBResource
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
# Resource
###########################################################################
captcha_datatype = Unicode(source='metadata', mandatory=True)


class Captcha(DBResource):
    
    class_id = 'config-captcha'
    class_version = '20110606'
    class_title = MSG(u'Captcha')
    class_description = MSG(u'Feature to protect from spammers')
    class_icon48 = 'icons/48x48/captcha.png'
    class_views = ['edit']

    class_schema = merge_dicts(
        DBResource.class_schema,
        captcha_question=captcha_datatype(
            default=u'2 + 3', title=MSG(u"Question")),
        captcha_answer=captcha_datatype(
            default=u'5', title=MSG(u"Answer")))

    edit = AutoEdit(
        title=MSG(u'Edit captcha'),
        fields=['captcha_question', 'captcha_answer'])


Configuration.register_plugin('captcha', Captcha)
