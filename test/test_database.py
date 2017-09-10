# -*- coding: UTF-8 -*-
# Copyright (C) 2016 Sylvain Taverne <taverne.sylvain@gmail.com>
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
from itools.database import AndQuery, PhraseQuery
from itools.fs import lfs

# Import from ikaaro
from ikaaro.database import Database
from ikaaro.folder import Folder
from ikaaro.server import Server, get_fake_context, create_server
from ikaaro.text import Text


class FreeTestCase(TestCase):

    def setUp(self):
        self.tearDown()
        create_server('test_database', 'test@hforge.org',
            'password', 'ikaaro', website_languages=['en', 'fr'])


    def tearDown(self):
        paths = ['test_database']
        for path in paths:
            if lfs.exists(path):
                lfs.remove(path)


    def get_database(self):
        size_min, size_max = 19500, 20500
        database = Database('test_database', size_min, size_max)
        context = get_fake_context(database)
        context.set_mtime = True
        root = database.get_resource('/')
        return root, context, database


    def test_create_text(self):
        root, context, database = self.get_database()
        # Create 1 resource
        resource = root.make_resource(None, Text)
        self.assertEqual(str(resource.abspath), '/0')
        metadata = resource.metadata
        self.assertEqual(metadata.format, 'text')
        database.save_changes()
        # Check if resource exists
        resource = root.get_resource('0')
        self.assertEqual(resource.name, '0')
        search = context.database.search(abspath='/0')
        self.assertEqual(len(search), 1)
        # Del resource
        root.del_resource('0')
        context.database.save_changes()
        # Check if has been removed
        resource = root.get_resource('0', soft=True)
        self.assertEqual(resource, None)
        search = context.database.search(abspath='/1')
        self.assertEqual(len(search), 0)
        # Close database
        database.close()


    def test_create_user(self):
        root, context, database = self.get_database()
        # Create a new user
        email = 'admin@hforge.org'
        password = 'password'
        user = root.make_user(email, password)
        self.assertEqual(user.name, '1')
        user.set_value('groups', ['/config/groups/admins'])
        database.save_changes()
        # Try to get user
        user = root.get_resource('/users/1', soft=True)
        self.assertEqual(user.name, '1')
        self.assertEqual(user.get_value('email'), 'admin@hforge.org')
        self.assertEqual(user.authenticate(password), True)
        self.assertEqual(user.authenticate('badpassword'), False)
        # Cannot create 2 users with the same email address
        user = root.make_user(email, password)
        self.assertEqual(user, None)


    def test_multilingual_search(self):
        root, context, database = self.get_database()
        # Create N resources
        for i in range(0, 20):
            kw =  {'title':   {'fr': u'Bonjour', 'en': u'Hello'}}
            root.make_resource(str(i), Text, **kw)
        database.save_changes()
        # Check if resource exists
        query = PhraseQuery('format', 'text')
        search = context.database.search(query)
        self.assertEqual(len(search), 20)
        # Check if resource exists
        query = AndQuery(
            PhraseQuery('format', 'text'),
            PhraseQuery('title', u'Hello'))
        search = context.database.search(query)
        self.assertEqual(len(search), 20)
        query = AndQuery(
            PhraseQuery('format', 'text'),
            PhraseQuery('title_en', u'Hello'))
        search = context.database.search(query)
        self.assertEqual(len(search), 20)
        query = AndQuery(
            PhraseQuery('format', 'text'),
            PhraseQuery('title_fr', u'Bonjour'))
        search = context.database.search(query)
        self.assertEqual(len(search), 20)
        query = AndQuery(
            PhraseQuery('format', 'text'),
            PhraseQuery('title_es', u'Hola'))
        search = context.database.search(query)
        self.assertEqual(len(search), 0)
        # Close database
        database.close()


    def test_move_file(self):
        root, context, database = self.get_database()
        kw =  {'title': {'fr': u'Bonjour', 'en': u'Hello'},
               'data': 'this is text'}
        resource = root.make_resource(None, Text, **kw)
        self.assertEqual(str(resource.abspath), '/0')
        database.save_changes()
        # Move '/0' to '/1'
        root.move_resource('0', '1')
        self.assertEqual(root.get_resource('0', soft=True), None)
        self.assertEqual(root.get_resource('1').name, '1')
        # Move '/1' to '/1'
        root.move_resource('1', '1')
        self.assertEqual(root.get_resource('1').name, '1')
        # Check text
        r1 = root.get_resource('1')
        data = r1.get_value('data').to_str()
        self.assertEqual(data, 'this is text')
        database.close()


    def test_move_folder(self):
        root, context, database = self.get_database()
        kw =  {'title': {'fr': u'Bonjour', 'en': u'Hello'}}
        container = root.make_resource('folder1', Folder, **kw)
        child = container.make_resource('child', Folder)
        child.make_resource('hello_child.txt', Text)
        container.make_resource('hello.txt', Text)
        self.assertEqual(
            context.database.added,
            set(['folder1.metadata', 'folder1/hello.txt.metadata',
                 'folder1/child.metadata', 'folder1/child/hello_child.txt.metadata']))
        root.move_resource('folder1', 'folder2')
        self.assertEqual(root.get_resource('folder1', soft=True), None)
        self.assertEqual(root.get_resource('folder2').name, 'folder2')
        self.assertEqual(root.get_resource('folder2/hello.txt').abspath, '/folder2/hello.txt')
        self.assertEqual(
            context.database.added,
            set(['folder2.metadata', 'folder2/hello.txt.metadata',
                 'folder2/child.metadata', 'folder2/child/hello_child.txt.metadata']))
        database.close()


    def test_abort_transaction(self):
        root, context, database = self.get_database()
        kw =  {'title': {'fr': u'Bonjour', 'en': u'Hello'},
               'data': 'this is text'}
        resource = root.make_resource(None, Text, **kw)
        self.assertEqual(str(resource.abspath), '/0')
        self.assertNotEqual(root.get_resource('/0'), None)
        database.save_changes()
        resource = root.make_resource(None, Text, **kw)
        self.assertEqual(str(resource.abspath), '/1')
        database.catalog.index_document({'abspath': '/2'})
        database.abort_changes()
        self.assertNotEqual(root.get_resource('/0'), None)
        self.assertEqual(root.get_resource('/1', soft=True), None)
        database.close()


    def test_close_transaction(self):
        """
        Test if flush is done when we close database
        """
        root, context, database = self.get_database()
        kw =  {'title': {'fr': u'Bonjour', 'en': u'Hello'},
               'data': 'this is text'}
        resource = root.make_resource(None, Text, **kw)
        self.assertEqual(str(resource.abspath), '/0')
        database.save_changes()
        query = PhraseQuery('format', 'text')
        search = context.database.search(query)
        self.assertEqual(len(search), 1)
        resource = root.make_resource(None, Text)
        database.close()
        root, context, database = self.get_database()
        query = PhraseQuery('format', 'text')
        search = context.database.search(query)
        self.assertEqual(len(search), 1)
        self.assertEqual(root.get_resource('/1', soft=True), None)



    def test_server(self):
        server = Server('test_database')
        root = server.database.get_resource('/')
        self.assertEqual(root.metadata.format, 'iKaaro')


    def test_create_folders(self):
        root, context, database = self.get_database()
        container = root.make_resource('folder', Folder)
        container.make_resource('1', Text)
        container.make_resource('2', Text)
        container.make_resource('3', Text)
        names = sorted(container.get_names())
        self.assertEqual(names, ['1', '2', '3'])


    def test_remove_folder(self):
        root, context, database = self.get_database()
        container = root.make_resource('folder', Folder)
        container.make_resource('1', Text)
        container.make_resource('2', Text)
        container.make_resource('3', Text)
        root.del_resource('folder')
        self.assertEqual(
            context.database.removed,
            set(['folder.metadata', 'folder/1.metadata',
                 'folder/2.metadata', 'folder/3.metadata']))
        self.assertEqual(root.get_resource('folder', soft=True), None)
        self.assertEqual(root.get_resource('folder/1', soft=True), None)
        self.assertEqual(root.get_resource('folder/2', soft=True), None)
        self.assertEqual(root.get_resource('folder/3', soft=True), None)


    def test_copy_folder(self):
        root, context, database = self.get_database()
        container = root.make_resource('folder1', Folder)
        container_child = container.make_resource('1', Folder)
        container_child.make_resource('subchild', Text)
        container.make_resource('2', Text)
        root.copy_resource('folder1', 'folder2')
        self.assertEqual(
            context.database.added,
            set([
              'folder1.metadata', 'folder1/1.metadata', 'folder1/1/subchild.metadata', 'folder1/2.metadata',
              'folder2.metadata', 'folder2/1.metadata', 'folder2/1/subchild.metadata', 'folder2/2.metadata',
              ]))



if __name__ == '__main__':
    main()
