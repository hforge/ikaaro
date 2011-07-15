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

# Import from standard library
import urllib, urllib2

# Import from itools
from itools.core import merge_dicts, thingy_lazy_property
from itools.datatypes import Enumerate, String, Unicode
from itools.gettext import MSG
from itools.web import get_context

# Import from ikaaro
from autoedit import AutoEdit
from autoform import TextWidget, Widget
from config import Configuration
from resource_ import DBResource
from utils import make_stl_template


###########################################################################
# ReCaptcha
###########################################################################

class RecaptchaWidget(Widget):

    title = MSG(u"Please enter the words below")

    template = make_stl_template(
        """
          <input type="hidden" name="${name}" value="Check"/>
          <script type="text/javascript">
          var RecaptchaOptions = {
            theme : 'clean'
          };
          </script>
          <script type="text/javascript"
              src="http://api.recaptcha.net/challenge?k=${public_key}"/>
          <noscript>
            <iframe src="http://api.recaptcha.net/noscript?k=${public_key}"
                height="300" width="500" frameborder="0"/><br/>
            <textarea name="recaptcha_challenge_field" rows="3" cols="40"/>
            <input type='hidden' name='recaptcha_response_field'
                value='manual_challenge'/>
          </noscript>
        """)


    def public_key(self):
        website = get_context().site_root
        captcha = website.get_resource('config/captcha')
        return captcha.get_property('recaptcha_public_key')




class RecaptchaDatatype(String):

    mandatory = True

    @classmethod
    def is_valid(cls, value):
        context = get_context()
        if getattr(context, 'recaptcha_return_code', None) == 'true':
            return True
        website = context.site_root
        captcha = website.get_resource('config/captcha')
        private_key = captcha.get_property('recaptcha_private_key')
        # Get remote ip
        remote_ip = context.get_remote_ip() or '127.0.0.1'
        # Get Captcha fields
        recaptcha_challenge_field = context.get_form_value(
            'recaptcha_challenge_field', type=String)
        recaptcha_response_field = context.get_form_value(
            'recaptcha_response_field', type=String)
        # Test if captcha value is valid
        params = urllib.urlencode ({
                'privatekey': private_key,
                'remoteip' :  remote_ip,
                'challenge':  recaptcha_challenge_field,
                'response' :  recaptcha_response_field,
                })
        request = urllib2.Request (
            url = "http://api-verify.recaptcha.net/verify",
            data = params,
            headers = {
                "Content-type": "application/x-www-form-urlencoded",
                "User-agent": "reCAPTCHA Python"
                }
            )
        httpresp = urllib2.urlopen (request)
        return_values = httpresp.read ().splitlines ();
        httpresp.close();
        context.recaptcha_return_code = return_code = return_values[0]
        return return_code == 'true'

###########################################################################
# Question Captcha
###########################################################################

class QuestionCaptchaDatatype(Unicode):
    mandatory = True


    @staticmethod
    def is_valid(value):
        website = get_context().site_root
        captcha = website.get_resource('config/captcha')
        return captcha.get_property('captcha_answer') == value



class QuestionCaptchaWidget(TextWidget):
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
# CaptchaWidget
###########################################################################
class CaptchaDatatype(Unicode):

    mandatory = True

    @staticmethod
    def is_valid(value):
        website = get_context().site_root
        captcha = website.get_resource('config/captcha')
        captcha_type = captcha.get_property('captcha_type')
        return CaptchaType.datatypes[captcha_type].is_valid(value)


class CaptchaWidget(Widget):


    @thingy_lazy_property
    def title(self):
        website = get_context().site_root
        captcha = website.get_resource('config/captcha')
        captcha_type = captcha.get_property('captcha_type')
        return CaptchaType.widgets[captcha_type].title


    def render(self, mode='events'):
        website = get_context().site_root
        captcha = website.get_resource('config/captcha')
        captcha_type = captcha.get_property('captcha_type')
        widget = CaptchaType.widgets[captcha_type]
        return widget(name=self.name, value=self.value).render()



###########################################################################
# Resource
###########################################################################

class CaptchaType(Enumerate):

    default = 'question'

    options = [{'name': 'question', 'value': MSG(u'Question captcha')},
               {'name': 'recaptcha', 'value': MSG(u'Recaptcha')}]

    widgets = {'question': QuestionCaptchaWidget,
               'recaptcha': RecaptchaWidget}

    datatypes = {'question': QuestionCaptchaDatatype,
                 'recaptcha': RecaptchaDatatype}


captcha_datatype = Unicode(source='metadata')


class Captcha(DBResource):

    class_id = 'config-captcha'
    class_title = MSG(u'Captcha')
    class_description = MSG(u'Feature to protect from spammers')
    class_icon48 = 'icons/48x48/captcha.png'

    class_schema = merge_dicts(
        DBResource.class_schema,
        captcha_type=CaptchaType(source='metadata', mandatory=True,
            title=MSG(u"Captcha type")),
        # Question captcha
        captcha_question=captcha_datatype(
            default=u'2 + 3', title=MSG(u"Question")),
        captcha_answer=captcha_datatype(
            default=u'5', title=MSG(u"Answer")),
        # ReCaptcha
        recaptcha_public_key=captcha_datatype(
                                title=MSG(u"Recaptcha public key")),
        recaptcha_private_key=captcha_datatype(
                                title=MSG(u"Recaptcha private key")))

    # Views
    class_views = ['edit']
    edit = AutoEdit(
        title=MSG(u'Edit captcha'),
        fields=['captcha_type',
                'captcha_question', 'captcha_answer',
                'recaptcha_public_key', 'recaptcha_private_key'])

    # Configuration
    config_name = 'captcha'
    config_group = 'access'


Configuration.register_plugin(Captcha)
