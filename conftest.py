from pathlib import Path
import pytest



BASE_HOST = 'https://example.jekins.io'


@pytest.fixture(scope='session')
def host():
    yield BASE_HOST


@pytest.fixture(scope='session')
def base_path():
    path = Path(__file__).absolute().parent
    yield str(path)


@pytest.fixture(scope='session')
def auth_data(host):
    yield host, 'example@mail.com', 'password'


@pytest.fixture
def api(auth_data):
    api = TestRailAPI(*auth_data)
    yield api

