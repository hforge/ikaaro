# -*- coding: UTF-8 -*-
# Copyright (C) 2017 Sylvain Taverne <taverne.sylvain@gmail.com>
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
from base64 import decodestring, encodestring
from copy import deepcopy
from datetime import datetime, timedelta
import json
from hashlib import sha224
from pytz import timezone
from urllib import quote, unquote

# Import from itools
from itools.core import freeze, proto_lazy_property
from itools.core import fixed_offset, is_prototype, local_tz
from itools.core import prototype
from itools.database.ro import ro_database
from itools.datatypes import String, HTTPDate
from itools.fs import lfs
from itools.i18n import has_language
from itools.i18n import format_datetime, format_date, format_time
from itools.i18n import AcceptLanguageType, format_number
from itools.log import log_warning
from itools.uri import normalize_path
from itools.uri import decode_query, get_reference, Path, Reference
from itools.web.context import get_form_value
from itools.web import ERROR
from itools.web.headers import get_type, Cookie, SetCookieDataType
from itools.web.utils import NewJSONEncoder, fix_json, reason_phrases

# Import from ikaaro
from skins import skin_registry


class CMSContext(prototype):

    accept_language = AcceptLanguageType.decode('')
    body = {}
    commit = True
    content_type = None
    cookies = {}
    database = None
    entity = None
    environ = {}
    form = {}
    form_error = None
    header_response = {}
    is_cron = False
    message = None
    method = None
    mtime = None # Last-Modified
    path_query_base = None
    query = {}
    request_time = 0
    resource = None
    root = None
    scripts = []
    server = None
    set_mtime = True
    soup_message = None
    status = None # response status
    styles = []
    uri = None
    user = None
    view = None

    #######################################################################
    # WSGI environ
    #######################################################################

    def init_from_environ(self, environ, user=None):
        from server import get_server
        # Set environ
        self.environ = environ
        path = environ.get('PATH_INFO')
        self.path = path
        self.header_response = {}
        self.content_type = None
        self.status = None
        # Get database
        server = get_server()
        self.server = server
        self.database = server.database
        # Root
        self.root = self.database.get_resource('/')
        # The request method
        self.method = environ.get('REQUEST_METHOD')
        # Get body
        self.body = self.get_body_from_environ()
        # The query
        query = environ.get('QUERY_STRING')
        self.query = decode_query(query)
        # Accept language
        accept_language = self.environ.get('HTTP_ACCEPT_LANGUAGE', '')
        if accept_language is None:
            accept_language = ''
        self.accept_language = AcceptLanguageType.decode(accept_language)
        # The URI as it was typed by the client
        xfp = environ.get('HTTP_X_FORWARDED_PROTO')
        src_scheme = xfp or 'http'
        xff = environ.get('HTTP_X-Forwarded-Host')
        if xff:
            xff = xff.split(',', 1)[0].strip()
        src_host = xff or environ.get('HTTP_HOST')
        if query:
            uri = '%s://%s%s?%s' % (src_scheme, src_host, path, query)
        else:
            uri = '%s://%s%s' % (src_scheme, src_host, path)
        self.uri = get_reference(uri)

        # Split the path into path and method ("a/b/c/;view")
        path = path if type(path) is Path else Path(path)
        name = path.get_name()
        if name and name[0] == ';':
            self.path = path[:-1]
            self.view_name = name[1:]
        else:
            self.path = path
            self.view_name = None

        # Cookies
        self.cookies = {}

        # Media files (CSS, javascript)
        # Set the list of needed resources. The method we are going to
        # call may need external resources to be rendered properly, for
        # example it could need an style sheet or a javascript file to
        # be included in the html head (which it can not control). This
        # attribute lets the interface to add those resources.
        self.styles = []
        self.scripts = []
        # Log user if user is given
        if user:
            self.login(user)
        # The authenticated user
        self.authenticate()
        # Search
        self._context_user_search = self._user_search(self.user)
        # The Site Root
        self.find_site_root()
        self.site_root.before_traverse(self)  # Hook
        # Not a cron
        self.is_cron = False
        # Set header
        self.set_header('Server', 'ikaaro.web')



    def on_request_end(self):
        pass


    @proto_lazy_property
    def timestamp(self):
        return datetime.utcnow().replace(tzinfo=fixed_offset(0))


    #######################################################################
    # Root
    #######################################################################

    @proto_lazy_property
    def root(self):
        return self.database.get_resource('/')


    def find_site_root(self):
        self.site_root = self.root

    #######################################################################
    # Templates API
    #######################################################################

    def get_template(self, web_path):
        warning = None
        web_path_object = Path(normalize_path(web_path))
        skin_name = web_path_object[1]
        try:
            skin = skin_registry[skin_name]
        except KeyError:
            warning = 'WARNING: web_path {} is obsolete use /ui/ikaaro/'
            warning = warning.format(web_path)
            web_path = web_path.replace('/ui/', '/ui/ikaaro/')
            skin = skin_registry['ikaaro']
        # 1) Try with envionment skin
        skin_key = skin.get_environment_key(self.server)
        web_path = web_path.replace(skin.base_path, '')
        template = self.get_template_from_skin_key(skin_key, web_path, warning)
        if template:
            return template
        # 2) Try with standard skin
        return self.get_template_from_skin_key(skin.key, web_path, warning)


    def get_template_from_skin_key(self, skin_key, web_path, warning):
        local_path = skin_key + web_path
        # 3. Get the handler
        handler = ro_database.get_handler(local_path, soft=True)
        if handler:
            if warning:
                print warning
            return handler

        # 4. Not an exact match: trigger language negotiation
        folder_path, name = local_path.rsplit('/', 1)
        name = name + '.'
        n = len(name)
        languages = []
        for x in lfs.get_names(folder_path):
            if x[:n] == name:
                language = x[n:]
                if has_language(language):
                    languages.append(language)
        if not languages:
            return None

        # 4.1 Get the best variant
        accept = self.accept_language
        language = accept.select_language(languages)
        # Print Warning
        if warning:
            print warning
        # 4.2 By default use whatever variant
        # (XXX we need a way to define the default)
        if language is None:
            language = languages[0]
        local_path = '%s.%s' % (local_path, language)
        return ro_database.get_handler(local_path, soft=True)


    #######################################################################
    # Request
    #######################################################################
    def get_request_line(self):
        #  XXX
        return ''


    def get_headers(self):
        #  XXX
        return ''


    def get_header(self, name):
        name = name.lower()
        datatype = get_type(name)
        if name == 'content-type':
            value = self.environ.get('CONTENT_TYPE')
        else:
            value = self.environ.get('HTTP_'+ name.upper())
        if value is None:
            return datatype.get_default() or ''
        try:
            return datatype.decode(value) or ''
        except ValueError:
            log_warning('malformed header: %s: %s' % (name, value),
                        domain='ikaaro.web')
            return datatype.get_default()


    def set_header(self, name, value):
        datatype = get_type(name)
        value = datatype.encode(value)
        self.header_response[name] = value


    def _set_header(self, name, value):
        """ Set header without encoding """
        self.header_response[name] = value


    def get_referrer(self):
        return self.get_header('referer')


    def get_form(self):
        if self.method in ('GET', 'HEAD'):
            return self.uri.query
        # XXX What parameters with the fields defined in the query?
        return self.body


    #######################################################################
    # Web response API
    #######################################################################

    def set_content_type(self, content_type, **kw):
        if type(content_type) is not str:
            raise TypeError('expected string, got %s' % repr(content_type))

        parameters = [ '; %s=%s' % x for x in kw.items() ]
        parameters = ''.join(parameters)
        self.content_type = content_type + parameters


    def set_content_disposition(self, disposition, filename=None):
        if filename:
            disposition = '%s; filename="%s"' % (disposition, filename)
        self._set_header('Content-Disposition', disposition)


    def set_default_response(self, status):
        # Build response
        self.status = status
        self.entity = '{0} {1}'.format(status, reason_phrases[status])
        self.set_content_type('text/plain')
        # Set response
        self.set_response_from_context()


    def set_response_from_context(self):
        # Accept cors
        if self.server.accept_cors:
            self.accept_cors()
        # Set default content type XXX ?
        if self.status == 304:
            # "NotModified" request
            # No status, content-type or other header should be added
            return
        if self.content_type is None:
            self.content_type = 'text/plain'
        # Set response body
        if self.entity is None:
            self.status = 204
            return
        elif isinstance(self.entity, Reference):
            location = self.uri.resolve(self.entity)
            location = str(location)
            self.entity = str(self.entity)
            self.status = 302
            self.set_header('Location', location)
            return
        # Never cache if status != 200
        if self.mtime and self.status != 200:
            self.set_header('Last-Modified', self.mtime)
            self.set_header('Cache-Control', 'max-age=1')


    #######################################################################
    # Cookies
    #######################################################################
    def get_cookie(self, name, datatype=None):
        value = None
        if name in self.cookies:
            # Case 1: the cookie was set in this request
            value = self.cookies[name].value
        else:
            # Case 2: read the cookie from the request
            cookies = self.get_header('cookie')
            if cookies:
                cookie = cookies.get(name)
                if cookie:
                    value = cookie.value

        if datatype is None:
            return value

        # Deserialize
        if value is None:
            return datatype.get_default()
        value = datatype.decode(value)
        if not datatype.is_valid(value):
            raise ValueError("Invalid cookie value")
        return value


    def set_cookie(self, name, value, **kw):
        # Build cookie
        self.cookies[name] = Cookie(value, **kw)
        # Set in headers
        cookies = SetCookieDataType.encode(self.cookies)
        self._set_header('Set-Cookie', cookies)


    def del_cookie(self, name):
        # Del cookie
        self.cookies[name] = Cookie('', max_age=0)
        # Set in headers
        cookies = SetCookieDataType.encode(self.cookies)
        self._set_header('Set-Cookie', cookies)

    #######################################################################
    # API / Forms
    #######################################################################
    def get_path_query_value(self, name, type=String, default=None):
        """Returns the value for the given name from the path query.
        """
        form = self.path_query_base
        return get_form_value(form, name, type, default)


    def get_query_value(self, name, type=String, default=None):
        """Returns the value for the given name from the query.  Useful for
        POST requests.
        """
        form = self.uri.query
        return get_form_value(form, name, type, default)


    def get_form_value(self, name, type=String, default=None):
        form = self.get_form()
        return get_form_value(form, name, type, default)


    def get_form_keys(self):
        return self.get_form().keys()


    def get_form_body(self, body):
        return decode_query(body)


    def get_json_body(self, body):
        data = json.loads(body)
        return fix_json(data)


    def get_body_from_environ(self):
        # Get content type
        response = self.get_header('content-type')
        try:
            content_type, type_parameters = response
        except:
            content_type = response
        # Case 1: nothing
        length = int(self.environ.get('CONTENT_LENGTH', '0'))
        body = self.environ['wsgi.input'].read(length)
        if not body:
            return {}
        # XXX
        if content_type == 'application/x-www-form-urlencoded':
            # Case 1: urlencoded
            return self.get_form_body(body)
        elif content_type == 'application/json':
            # Case 2: json
            return self.get_json_body(body)
        elif content_type.startswith('multipart/'):
            # Case 3: multipart
            return self.get_multipart_body(body)
        # Case 4: Not managed content type
        raise ValueError('Invalid content type "{0}"'.format(content_type))


    def get_multipart_body(self, body):
        from itools.web.entities import Entity
        content_type, type_parameters = self.get_header('content-type')
        boundary = type_parameters.get('boundary')
        boundary = '--%s' % boundary
        form = {}
        for part in body.split(boundary)[1:-1]:
            # Parse the entity
            entity = Entity(string=part)
            # Find out the parameter name
            header = entity.get_header('Content-Disposition')
            value, header_parameters = header
            name = header_parameters['name']
            # Load the value
            body = entity.get_body()
            if 'filename' in header_parameters:
                filename = header_parameters['filename']
                if filename:
                    # Strip the path (for IE).
                    filename = filename.split('\\')[-1]
                    # Default content-type, see
                    # http://tools.ietf.org/html/rfc2045#section-5.2
                    if entity.has_header('content-type'):
                        mimetype = entity.get_header('content-type')[0]
                    else:
                        mimetype = 'text/plain'
                    form[name] = filename, mimetype, body
                else:
                    form[name] = None
            else:
                if name not in form:
                    form[name] = body
                else:
                    if isinstance(form[name], list):
                        form[name].append(body)
                    else:
                        form[name] = [form[name], body]
        return form

    #######################################################################
    # ACL API
    #######################################################################

    def is_access_allowed(self, resource, view, user=None):
        """Returns True if the given user is allowed to access the given
        method of the given resource. False otherwise.
        """
        if user is None:
            user = self.user

        # Get the access control definition (default to False)
        if view is None:
            return False
        access = getattr(view, 'access_%s' % self.method, view.access)

        # Private (False) or Public (True)
        if type(access) is bool:
            return access

        # Only booleans and strings are allowed
        if type(access) is not str:
            raise TypeError('unexpected value "%s"' % access)

        # Access Control through a method
        method = getattr(self.root, access, None)
        if method is None:
            raise ValueError('access control "%s" not defined' % access)

        return method(user, resource)

    #######################################################################
    # Search
    #######################################################################
    def _user_search(self, user):
        access = self.root.get_resource('/config/access')
        query = access.get_search_query(user, 'view')
        return self.database.search(query)


    @proto_lazy_property
    def _context_user_search(self):
        return self._user_search(self.user)


    def search(self, query=None, user=None, **kw):
        if self.is_cron:
            # If the search is done by a CRON we don't
            # care about the default ACLs rules
            return self.database.search(query)
        if user is None:
            return self._context_user_search.search(query, **kw)
        return self._user_search(user).search(query, **kw)

    #######################################################################
    # Login API
    #######################################################################

    def login(self, user):
        user_id = user.get_user_id()
        user_token = user.get_auth_token()

        # Make cookie
        token = self._get_auth_token(user_token)
        cookie = '%s:%s' % (user_id, token)
        cookie = quote(encodestring(cookie))
        self._set_auth_cookie(cookie)

        # Set the user
        self.user = user


    def logout(self):
        self.del_cookie('iauth')
        self.user = None


    def _set_auth_cookie(self, cookie):
        # Compute expires datetime (FIXME Use the request date)
        session_timeout = self.server.session_timeout
        if session_timeout != timedelta(0):
            expires = self.timestamp + session_timeout
            expires = HTTPDate.encode(expires)
        else:
            expires = None
        expires = None

        # Set cookie
        self.set_cookie('iauth', cookie, path='/', expires=expires)


    def _get_auth_token(self, user_token):
        # We use the header X-User-Agent or User-Agent
        ua = self.get_header('X-User-Agent')
        if not ua:
            ua = self.get_header('User-Agent')
        token = '%s:%s' % (user_token, ua)
        return sha224(token).digest()


    def authenticate(self):
        """Checks the authentication credentials and sets the context user if all
        checks are ok.
        """
        self.user = None

        # 1. Get credentials with username and token
        try:
            username, token = self.get_authentication_credentials()
        except ValueError as error:
            msg = "Authentication error : %s " % error.message
            log_warning(msg, domain='ikaaro.web')
            return

        if not username or not token:
            return

        # 2. Get the user
        user = self.root.get_user(username)
        if not user:
            return

        # 3. Check the token
        user_token = user.get_auth_token()
        if token == self._get_auth_token(user_token):
            self.user = user


    def get_authentication_credentials(self):
        """Try to get credentials from Authorization header or Cookies"""

        # Check for credential in headers
        auth_header = self.get_header('Authorization')
        if auth_header:
            # Parse the header credentials
            auth_type, b64_credentials = auth_header
        else:
            # No Authorization header, get credentials in cookies
            b64_credentials = self.get_cookie('iauth')

        if not b64_credentials:
            # No credentials found
            return None, None

        # Try to return the decoded credentials
        try:
            credentials = decodestring(unquote(b64_credentials))
        except Exception:
            raise ValueError('bad credentials "%s"' % b64_credentials)

        return credentials.split(':', 1)


    #######################################################################
    # Tools API
    #######################################################################

    def agent_is_a_robot(self):
        return False


    def get_remote_ip(self):
        remote_ip = self.get_header('X-Forwarded-For')
        return remote_ip.split(',', 1)[0].strip() if remote_ip else None


    def get_link(self, resource):
        """Return a link to the given resource, from the given context.
        """
        abspath = deepcopy(resource.abspath)
        abspath.endswith_slash = False
        return str(abspath)


    def return_json(self, data, status=None):
        if status:
            self.status = status
        self.entity = json.dumps(data, cls=NewJSONEncoder)
        self.set_content_type('application/json')
        return self.entity


    def come_back(self, message, goto=None, keep=freeze([]), **kw):
        """This is a handy method that builds a resource URI from some
        parameters.  It exists to make short some common patterns.
        """
        # By default we come back to the referrer
        if goto is None:
            goto = self.get_referrer()
            # Replace goto if no referrer
            if goto is None:
                goto = str(self.uri)
                if '/;' in goto:
                    goto = goto.split('/;')[0]

        if type(goto) is str:
            goto = get_reference(goto)

        # Preserve some form values
        form = {}
        for key, value in self.get_form().items():
            # Be robust
            if not key:
                continue
            # Omit methods
            if key[0] == ';':
                continue
            # Omit files
            if isinstance(value, tuple) and len(value) == 3:
                continue
            # Keep form field
            if (keep is True) or (key in keep):
                form[key] = value
        if form:
            goto = goto.replace(**form)
        # Translate the source message
        if message:
            text = message.gettext(**kw)
            if is_prototype(message, ERROR):
                goto = goto.replace(error=text)
            else:
                goto = goto.replace(info=text)
        # Keep fancybox
        if 'fancybox' in self.uri.query:
            goto.query['fancybox'] = '1'
        # Ok
        return goto

    #######################################################################
    # API i18n
    #######################################################################

    def fix_tzinfo(self, datetime, tz=None):
        if tz is None and self.user:
            tz = self.user.get_timezone()

        # 1. Build the tzinfo object
        tzinfo = timezone(tz) if tz else local_tz

        # 2. Change datetime
        if datetime.tzinfo:
            datetime = datetime.astimezone(tzinfo)
        else:
            datetime = tzinfo.localize(datetime)

        return datetime


    def format_datetime(self, datetime, tz=None):
        datetime = self.fix_tzinfo(datetime, tz)
        # Ok
        return format_datetime(datetime, accept=self.accept_language)


    def format_date(self, date):
        return format_date(date, accept=self.accept_language)


    def format_time(self, time):
        return format_time(time, accept=self.accept_language)


    def format_number(self, number, places=2, curr='', pos=u'', neg=u'-',
            trailneg=u""):
        return format_number(number, places=places, curr=curr, pos=pos,
                neg=neg, trailneg=trailneg, accept=self.accept_language)
