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
from itools.datatypes import String
from itools.fs import lfs
from itools.web.views import ItoolsView

# Import from ikaaro
from ikaaro.server import Server, create_server


SERVER = None
DATABASE_TEST_PATH = '/tmp/www.hforge.org'


class TestHTML_View(ItoolsView):

    access = True

    def GET(self, query, context):
        return 'hello world'


class TestPlainText_View(ItoolsView):

    access = True

    def GET(self, query, context):
        context.set_content_type('text/plain')
        return 'hello world'


class TestJson_View(ItoolsView):

    access = True

    def GET(self, query, context):
        kw = {'text': 'hello world'}
        return self.return_json(kw, context)



class ServerTestCase(TestCase):

    def setUp(self):
        global SERVER
        if SERVER is not None:
            return
        self.tearDown()
        path = DATABASE_TEST_PATH
        email = 'test@example.com'
        password = 'password'
        root = None
        modules = []
        listen_port = 8081
        create_server(path, email, password, root,  modules, listen_port)
        server = Server(path)
        server.start(detach=False, loop=False)
        SERVER = server


    def test_server_ctrl(self):
        server = SERVER
        # Test /;ctrl view
        retour = server.do_request('GET', '/;_ctrl')
        self.assertEqual(retour['status'], 200)


    def test_server_up(self):
        server = SERVER
        retour = server.do_request('GET', '/api/status', as_json=True)
        self.assertEqual(retour['entity']['up'], True)


    def test_server_404(self):
        server = SERVER
        retour = server.do_request('GET', '/api/404', as_json=True)
        self.assertEqual(retour['status'], 404)


    # FIXME
    #def test_server_forbidden(self):
    #    server = SERVER
    #    server.dispatcher.add('/test/forbidden', TestPlainText_View(access=False))
    #    user = server.root.get_resource('/users/0')
    #    retour = server.do_request('GET', '/test/forbidden',
    #          as_json=True, user=user)
    #    self.assertEqual(retour['status'], 403)


    def test_server_unauthorized(self):
        server = SERVER
        server.dispatcher.add('/test/unauthorized', TestPlainText_View(access=False))
        retour = server.do_request('GET', '/test/unauthorized')
        self.assertEqual(retour['status'], 401)


    def test_html(self):
        server = SERVER
        server.dispatcher.add('/test/html', TestHTML_View)
        retour = server.do_request('GET', '/test/html')
        self.assertEqual(retour['status'], 200)
        self.assertEqual(retour['context'].content_type, 'text/html; charset=UTF-8')


    def test_plain_text(self):
        server = SERVER
        server.dispatcher.add('/test/text', TestPlainText_View)
        retour = server.do_request('GET', '/test/text')
        self.assertEqual(retour['status'], 200)
        self.assertEqual(retour['entity'], 'hello world')


    def test_json(self):
        server = SERVER
        server.dispatcher.add('/test/json', TestJson_View)
        retour = server.do_request('GET', '/test/json', as_json=True)
        self.assertEqual(retour['status'], 200)
        self.assertEqual(retour['entity'], {'text': 'hello world'})


    def test_stop_server(self):
        server = SERVER
        server.stop()
        # Remove database
        path = DATABASE_TEST_PATH
        if lfs.exists(path):
            lfs.remove(path)



if __name__ == '__main__':
    main()
