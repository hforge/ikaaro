from itools.database import PhraseQuery
from ikaaro.database import Database


async def test_query(demo):
    with Database(demo, 19500, 20500) as database:
        async with database.init_context():
#           root = database.get_resource('/')
            # Root
            search = database.search(PhraseQuery('abspath', '/'))
            assert len(search) == 1
            # Users
            search = database.search(PhraseQuery('format', 'user'))
            assert len(search) > 0
            for doc in search.get_documents():
                path = doc.get_value('abspath')
                search = database.search(PhraseQuery('abspath', path))
                assert len(search) == 1
                doc = search.get_documents()[0]
                assert doc.get_value('abspath') == path
