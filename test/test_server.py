# -*- coding: UTF-8 -*-
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

# Import from the Standard Library
from unittest import TestCase, main

# Import from itools
from itools.database import PhraseQuery
from itools.datatypes import String, Unicode
from itools.web.views import ItoolsView, BaseView

# Import from ikaaro
from ikaaro.server import Server


class TestHTML_View(ItoolsView):

    access = True
    known_methods = ['GET']

    def GET(self, resource, context):
        return 'hello world'


class TestPlainText_View(ItoolsView):

    access = True
    known_methods = ['GET']

    def GET(self, resource, context):
        context.set_content_type('text/plain')
        return 'hello world'



class TestJson_View(ItoolsView):

    access = True
    known_methods = ['GET']

    query_schema = {'name': String}
    def GET(self, resource, context):
        kw = {'text': 'hello '+ context.query.get('name')}
        return self.return_json(kw, context)



class TestJsonAction_View(BaseView):

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



class ServerTestCase(TestCase):


    def test_server_ctrl(self):
        with Server('demo.hforge.org') as server:
            with server.database.init_context():
                # Test /;ctrl view
                retour = server.do_request('GET', '/;_ctrl')
                self.assertEqual(retour['status'], 200)


    #def test_server_ctrl2(self):
    #    """ We should be able to do this kind of tests"""
    #    import requests
    #    with Server('demo.hforge.org') as server:
    #        server.start(loop=False)
    #        r = requests.get('http://localhost:8080/;_ctrl')
    #        self.assertEqual(r.status_code, 200)


    def test_server_up(self):
        with Server('demo.hforge.org') as server:
            with server.database.init_context():
                retour = server.do_request('GET', '/api/status', as_json=True)
                self.assertEqual(retour['entity']['up'], True)


    def test_server_404(self):
        with Server('demo.hforge.org') as server:
            with server.database.init_context():
                # Error 404 json
                retour = server.do_request('GET', '/api/404', as_json=True)
                self.assertEqual(retour['status'], 404)
                self.assertEqual(retour['entity']['code'], 404)
                self.assertEqual(retour['context'].content_type, 'application/json')
                # Error 404 web
                retour = server.do_request('GET', '/api/404', as_json=False)
                self.assertEqual(retour['status'], 404)
                self.assertEqual(retour['context'].content_type, 'text/html; charset=UTF-8')


    def test_server_unauthorized(self):
        with Server('demo.hforge.org') as server:
            with server.database.init_context():
                server.dispatcher.add('/test/unauthorized', TestPlainText_View(access=False))
                retour = server.do_request('GET', '/test/unauthorized')
                self.assertEqual(retour['status'], 401)


    def test_html(self):
        with Server('demo.hforge.org') as server:
            with server.database.init_context():
                server.dispatcher.add('/test/html', TestHTML_View)
                retour = server.do_request('GET', '/test/html')
                self.assertEqual(retour['status'], 200)
                self.assertEqual(retour['context'].content_type, 'text/html; charset=UTF-8')


    def test_plain_text(self):
        with Server('demo.hforge.org') as server:
            with server.database.init_context():
                server.dispatcher.add('/test/text', TestPlainText_View)
                retour = server.do_request('GET', '/test/text')
                self.assertEqual(retour['status'], 200)
                self.assertEqual(retour['entity'], 'hello world')


    def test_json(self):
        with Server('demo.hforge.org') as server:
            with server.database.init_context():
                server.dispatcher.add('/test/json', TestJson_View)
                retour = server.do_request('GET', '/test/json?name=world', as_json=True)
                self.assertEqual(retour['status'], 200)
                self.assertEqual(retour['entity'], {'text': 'hello world'})


    def test_action(self):
        with Server('demo.hforge.org') as server:
            with server.database.init_context():
                server.dispatcher.add('/test/json-action', TestJsonAction_View)
                body = {'action': 'hello', 'name': 'world'}
                retour = server.do_request('POST', '/test/json-action', body=body, as_json=True)
                self.assertEqual(retour['entity'], {'text': 'hello world'})
                body = {'action': 'hello', 'name': 'sylvain'}
                retour = server.do_request('POST', '/test/json-action', body=body, as_json=True)
                self.assertEqual(retour['entity'], {'text': 'hello sylvain'})


    #def test_upload_file(self):
    #    with Server('demo.hforge.org') as server:
    #        with server.database.init_context(username='0'):
    #            root = server.database.get_resource('/')
    #            data = 'file.txt', StringIO('hello world'), 'text/plain'
    #            body = {'title:en': u'My file', 'data': data}
    #            retour = server.do_request('POST', '/;new_resource?type=file', body=body, as_multipart=True)
    #            self.assertEqual(retour['status'], 302)
    #            new_r = root.get_resource('my-file')
    #            handler = new_r.get_value('data')
    #            self.assertEqual(handler.to_str(), 'hello world')


    def test_commit(self):
        with Server('demo.hforge.org') as server:
            with server.database.init_context():
                server.dispatcher.add('/test/json-action', TestJsonAction_View)
                body = {'action': 'set_root_title', 'title': u'Sylvain'}
                retour = server.do_request('POST', '/test/json-action', body=body, as_json=True)
                self.assertEqual(retour['status'], 200)
                self.assertEqual(retour['entity']['success'], True)
                self.assertEqual(server.root.get_value('title', language='fr'), u'Sylvain')
                body = {'action': 'set_root_title', 'title': u'Zidane'}
                retour = server.do_request('POST', '/test/json-action', body=body, as_json=True)
                self.assertEqual(retour['status'], 200)
                self.assertEqual(retour['entity']['success'], True)
                self.assertEqual(server.root.get_value('title', language='fr'), u'Zidane')


    def test_catalog_access(self):
        query = PhraseQuery('format', 'user')
        with Server('demo.hforge.org') as server:
            with server.database.init_context() as context:
                self.assertEqual(context.user, None)
                search = context.search(query)
                self.assertEqual(len(search), 0)
        #with Server('demo.hforge.org') as server:
        #    with server.database.init_context(username='0') as context:
        #        self.assertEqual(context.user, None)
        #        search = context.search(query)
        #        self.assertNotEqual(len(search), 0)


    def test_server_login_test_server(self):
        with Server('demo.hforge.org') as server:
            with server.database.init_context():
                server.dispatcher.add('/test/401', TestPlainText_View(access='is_admin'))
                retour = server.do_request('GET', '/test/401')
                self.assertEqual(retour['status'], 401)
        #with Server('demo.hforge.org') as server:
        #    with server.database.init_context(username='0') as context:
        #        self.assertEqual(context.user.name, '0')
        #        is_admin = context.root.is_admin(context.user, context.root)
        #        self.assertEqual(is_admin, True)
        #        server.dispatcher.add('/test/unauthorized', TestPlainText_View(access='is_admin'))
        #        retour = server.do_request('GET', '/test/unauthorized')
        #        self.assertEqual(retour['status'], 200)



if __name__ == '__main__':
    main()
