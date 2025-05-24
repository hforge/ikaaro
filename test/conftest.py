import pathlib
import shutil

import pytest

# Import from itools
from itools.fs import lfs

# Import from ikaaro
from ikaaro.database import Database
from ikaaro.server import Server, create_server


BASE_DIR = pathlib.Path(__file__).resolve().parent


@pytest.fixture(scope='session')
def demo():
    path = str(BASE_DIR / 'demo.hforge.org')
    if lfs.exists(path):
        lfs.remove(path)

    create_server(path, 'test@hforge.org', 'password', 'ikaaro',
                  website_languages=['en', 'fr'])

    return path


@pytest.fixture
def database(demo):
    with Database(demo, 19500, 20500) as database:
        yield database


@pytest.fixture
def server(demo):
    with Server(demo) as server:
        yield server


@pytest.fixture
def hforge_server():
    path = str(BASE_DIR / 'www.hforge.org')
    email = 'test@example.com'
    password = 'password'
    root = None
    modules = None
    listen_port = 8081

    if modules is None:
        modules = []

    shutil.rmtree(path, ignore_errors=True)
    shutil.rmtree('sessions', ignore_errors=True)
    create_server(
        target=path,
        email=email,
        password=password,
        root=root,
        modules=modules,
        listen_port=listen_port,
        backend="git"
    )
    server = Server(path)
    return server
