from unittest import TestCase, main

from itools.database import PhraseQuery
from ikaaro.database import Database


class QueryTestCase(TestCase):

    def test_query(self):
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
#               root = database.get_resource('/')
                # Root
                search = database.search(PhraseQuery('abspath', '/'))
                self.assertEqual(len(search), 1)
                # Users
                search = database.search(PhraseQuery('format', 'user'))
                self.assertTrue(len(search) > 0)
                for doc in search.get_documents():
                    path = doc.get_value('abspath')
                    search = database.search(PhraseQuery('abspath', path))
                    self.assertEqual(len(search), 1)
                    doc = search.get_documents()[0]
                    self.assertEqual(doc.get_value('abspath'), path)


if __name__ == '__main__':
    main()
