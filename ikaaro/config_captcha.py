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
from itools.core import proto_lazy_property
from itools.datatypes import Enumerate, String, Unicode
from itools.gettext import MSG
from itools.web import get_context

# Import from ikaaro
from autoedit import AutoEdit
from autoform import TextWidget, RadioWidget, Widget
from config import Configuration
from fields import Field, Select_Field, Text_Field
from folder import Folder
from resource_ import DBResource
from utils import make_stl_template


captcha_field = Text_Field(multilingual=False)

###########################################################################
# ReCaptcha
###########################################################################

class RecaptchaWidget(Widget):

    title = MSG(u"Please enter the words below")
    public_key = None

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




class RecaptchaDatatype(String):

    mandatory = True
    private_key = None

    def is_valid(cls, value):
        context = get_context()
        if getattr(context, 'recaptcha_return_code', None) == 'true':
            return True
        # Get remote ip
        remote_ip = context.get_remote_ip() or '127.0.0.1'
        # Get Captcha fields
        recaptcha_challenge_field = context.get_form_value(
            'recaptcha_challenge_field', type=String)
        recaptcha_response_field = context.get_form_value(
            'recaptcha_response_field', type=String)
        # Test if captcha value is valid
        params = urllib.urlencode ({
                'privatekey': cls.private_key,
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



class Captcha_Recaptcha(DBResource):

    class_id = 'config-captcha-recaptcha'
    class_title = MSG(u'Recaptcha')
    class_views = ['edit']

    # Fields
    public_key = captcha_field(title=MSG(u"Recaptcha public key"))
    private_key = captcha_field(title=MSG(u"Recaptcha private key"))

    # Views
    edit = AutoEdit(fields=['public_key', 'private_key'])

    # API
    def get_widget(self):
        return RecaptchaWidget(public_key=self.get_value('public_key'))


    def get_datatype(self):
        return RecaptchaDatatype(private_key=self.get_value('private_key'))


###########################################################################
# Question Captcha
###########################################################################

class QuestionCaptchaDatatype(Unicode):

    mandatory = True
    answer = None

    def is_valid(cls, value):
        return cls.answer == value



class QuestionCaptchaWidget(TextWidget):

    title = MSG(u"Please answer the question below:")

    question = None
    template = make_stl_template("""
    ${question}
    <input type="text" id="${id}" name="${name}" value="${value}"
      maxlength="${maxlength}" size="${size}" />""")




class Captcha_Question(DBResource):

    class_id = 'config-captcha-question'
    class_title = MSG(u'Captcha question')
    class_views = ['edit']

    # Fields
    question = captcha_field(default=u'2 + 3', title=MSG(u"Question"))
    answer = captcha_field(default=u'5', title=MSG(u"Answer"))

    # Views
    edit = AutoEdit(fields=['question', 'answer'])

    # API
    def get_widget(self):
        return QuestionCaptchaWidget(question=self.get_value('question'))


    def get_datatype(self):
        return QuestionCaptchaDatatype(answer=self.get_value('answer'))



###########################################################################
# CaptchaWidget
###########################################################################

class CaptchaDatatype(Unicode):

    mandatory = True

    def is_valid(cls, value):
        root = get_context().root
        config_captcha = root.get_resource('config/captcha')
        captcha = config_captcha.get_captcha()
        datatype = captcha.get_datatype()
        return datatype.is_valid(value)



class CaptchaWidget(Widget):

    @proto_lazy_property
    def title(self):
        root = get_context().root
        config_captcha = root.get_resource('config/captcha')
        captcha = config_captcha.get_captcha()
        widget = captcha.get_widget()
        return widget.title


    def render(self, mode='events'):
        root = get_context().root
        config_captcha = root.get_resource('config/captcha')
        captcha = config_captcha.get_captcha()
        widget = captcha.get_widget()
        return widget(name=self.name, value=self.value).render()



class Captcha_Field(Field):

    required = True
    datatype = CaptchaDatatype
    widget = CaptchaWidget



###########################################################################
# Captcha Config
###########################################################################
class Select_CaptchaWidget(RadioWidget):

    template = make_stl_template("""
    <stl:block stl:repeat="option options">
      <input type="radio" id="${id}-${option/name}" name="${name}"
        value="${option/name}" checked="${option/selected}" />
      <label for="${id}-${option/name}">
          <a href="${option/name}">
          ${option/value}
          </a>
      </label>
      <br stl:if="not oneline" />
    </stl:block>""")



class CaptchaType(Enumerate):

    default = 'question'

    options = [
        {'name': 'question', 'value': MSG(u'Question captcha')},
        {'name': 'recaptcha', 'value': MSG(u'Recaptcha')}]



class Captcha(Folder):

    class_id = 'config-captcha'
    class_title = MSG(u'Captcha')
    class_description = MSG(u'Feature to protect from spammers')
    class_icon48 = 'icons/48x48/captcha.png'

    # Fields
    captcha_type = Select_Field(
        required=True, title=MSG(u"Captcha type"), datatype=CaptchaType,
        widget = Select_CaptchaWidget(has_empty_option=False))

    # Views
    class_views = ['edit']
    edit = AutoEdit(title=MSG(u'Edit captcha'), fields=['captcha_type'])

    # Configuration
    config_name = 'captcha'
    config_group = 'access'


    def init_resource(self, **kw):
        super(Captcha, self).init_resource(**kw)
        # Init several captcha
        self.make_resource('question', Captcha_Question)
        self.make_resource('recaptcha', Captcha_Recaptcha)


    def get_captcha(self):
        captcha_type = self.get_value('captcha_type')
        return self.get_resource(captcha_type)


# Register captcha
Configuration.register_module(Captcha)
