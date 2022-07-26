import pytest
from duck_jenkins import JenkinsData
import os
import shutil

BASE_HOST = 'example.jenkins.io'
WORKING_DIR = './temp'


@pytest.fixture(scope='session')
def host():
    yield BASE_HOST


@pytest.fixture(scope='session')
def auth_data(host):
    yield {
        'domain_name': host,
        'data_directory': WORKING_DIR,
        'verify_ssl': 'password',
        'user_id': 'john',
        'secret': 'password'
    }


@pytest.fixture(autouse=True)
def run_around_tests():
    delete_dir = WORKING_DIR
    if os.path.exists(delete_dir):
        shutil.rmtree(delete_dir)
    os.makedirs(delete_dir)
    yield

@pytest.fixture
def jenkins_data(auth_data):
    jd = JenkinsData(**auth_data)
    yield jd
