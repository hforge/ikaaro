# Copyright (C) 2017 Alexandre Bonny <alexandre.bonny@protonmail.com>
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

import io

import pytest
import requests

# Import from itools
from itools.database import PhraseQuery
from itools.datatypes import String, Unicode
from itools.web.views import ItoolsView, BaseView

# Import from ikaaro
from ikaaro.server import Server


class HTML_View(ItoolsView):

    access = True
    known_methods = ['GET']

    def GET(self, resource, context):
        return 'hello world'


class PlainText_View(ItoolsView):

    access = True
    known_methods = ['GET']

    def GET(self, resource, context):
        context.set_content_type('text/plain')
        return 'hello world'


class Json_View(ItoolsView):

    access = True
    known_methods = ['GET']

    query_schema = {'name': String}
    def GET(self, resource, context):
        kw = {'text': 'hello '+ context.query.get('name')}
        return self.return_json(kw, context)



class JsonAction_View(BaseView):

    access = True
    known_methods = ['GET', 'POST']

    schema = {'name': String}
    def action_hello(self, resource, context, form):
        kw = {'text': 'hello '+ form.get('name')}
        return self.return_json(kw, context)


    action_set_root_title_schema = {'title': Unicode}
    def action_set_root_title(self, resource, context, form):
        root = context.root
        root.set_value('title', form.get('title'), language='fr')
        kw = {'success': True}
        return self.return_json(kw, context)



async def test_server_ctrl(server):
    async with server.database.init_context():
        # Test /;ctrl view
        retour = server.do_request('GET', '/;_ctrl')
        assert retour['status'] == 200


@pytest.mark.xfail
def test_server_ctrl2(server):
    """ We should be able to do this kind of tests"""
    server.start(loop=False)
    r = requests.get('http://localhost:8080/;_ctrl')
    assert r.status_code == 200


async def test_server_up(server):
    async with server.database.init_context():
        retour = server.do_request('GET', '/api/status', as_json=True)
        assert retour['entity']['up'] is True


async def test_server_404(server):
    async with server.database.init_context():
        # Error 404 json
        retour = server.do_request('GET', '/api/404', as_json=True)
        assert retour['status'] == 404
        assert retour['entity']['code'] == 404
        assert retour['context'].content_type == 'application/json'
        # Error 404 web
        retour = server.do_request('GET', '/api/404', as_json=False)
        assert retour['status'] == 404
        assert retour['context'].content_type == 'text/html; charset=UTF-8'


async def test_server_unauthorized(server):
    async with server.database.init_context():
        server.dispatcher.add('/test/unauthorized', PlainText_View(access=False))
        retour = server.do_request('GET', '/test/unauthorized')
        assert retour['status'] == 401


async def test_html(server):
    async with server.database.init_context():
        server.dispatcher.add('/test/html', HTML_View)
        retour = server.do_request('GET', '/test/html')
        assert retour['status'] == 200
        assert retour['context'].content_type == 'text/html; charset=UTF-8'


async def test_plain_text(server):
    async with server.database.init_context():
        server.dispatcher.add('/test/text', PlainText_View)
        retour = server.do_request('GET', '/test/text')
        assert retour['status'] == 200
        assert retour['entity'] == 'hello world'


async def test_json(server):
    async with server.database.init_context():
        server.dispatcher.add('/test/json', Json_View)
        retour = server.do_request('GET', '/test/json?name=world', as_json=True)
        assert retour['status'] == 200
        assert retour['entity'] == {'text': 'hello world'}


async def test_action(server):
    async with server.database.init_context():
        server.dispatcher.add('/test/json-action', JsonAction_View)
        body = {'action': 'hello', 'name': 'world'}
        retour = server.do_request('POST', '/test/json-action', body=body, as_json=True)
        assert retour['entity'] == {'text': 'hello world'}
        body = {'action': 'hello', 'name': 'sylvain'}
        retour = server.do_request('POST', '/test/json-action', body=body, as_json=True)
        assert retour['entity'] == {'text': 'hello sylvain'}


@pytest.mark.xfail
async def test_upload_file(server):
    async with server.database.init_context(username='0'):
        root = server.database.get_resource('/')
        data = 'file.txt', io.StringIO('hello world'), 'text/plain'
        body = {'title:en': u'My file', 'data': data}
        retour = server.do_request('POST', '/;new_resource?type=file', body=body, as_multipart=True)
        assert retour['status'] == 302
        new_r = root.get_resource('my-file')
        handler = new_r.get_value('data')
        assert handler.to_str() == 'hello world'


async def test_commit(server):
    async with server.database.init_context():
        server.dispatcher.add('/test/json-action', JsonAction_View)
        body = {'action': 'set_root_title', 'title': 'Sylvain'}
        retour = server.do_request('POST', '/test/json-action', body=body, as_json=True)
        assert retour['status'] == 200
        assert retour['entity']['success'] is True
        assert server.root.get_value('title', language='fr') == 'Sylvain'
        body = {'action': 'set_root_title', 'title': 'Zidane'}
        retour = server.do_request('POST', '/test/json-action', body=body, as_json=True)
        assert retour['status'] == 200
        assert retour['entity']['success'] is True
        assert server.root.get_value('title', language='fr') == 'Zidane'


async def test_catalog_access(demo):
    query = PhraseQuery('format', 'user')
    with Server(demo) as server:
        async with server.database.init_context() as context:
            assert context.user is None
            search = context.search(query)
            assert len(search) == 0

#   with Server(demo) as server:
#       async with server.database.init_context(username='0') as context:
#           assert context.user is None
#           search = context.search(query)
#           assert len(search) > 0


async def test_server_login_test_server(demo):
    with Server(demo) as server:
        async with server.database.init_context():
            server.dispatcher.add('/test/401', PlainText_View(access='is_admin'))
            retour = server.do_request('GET', '/test/401')
            assert retour['status'] == 401

    with Server(demo) as server:
        async with server.database.init_context(username='0') as context:
            assert context.user.name == '0'
            is_admin = context.root.is_admin(context.user, context.root)
            assert is_admin is True
            server.dispatcher.add('/test/unauthorized', PlainText_View(access='is_admin'))
            retour = server.do_request('GET', '/test/unauthorized')
            assert retour['status'] == 200
