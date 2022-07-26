import responses
import duckdb
from duck_jenkins._model import Cause, Jenkins
from tests import get_build_info
import os


@responses.activate
def test_cause():
    db = duckdb.connect()
    cursor = db.cursor()
    jenkins = Jenkins.assign_cursor(cursor).factory('jenkins.testing.io')
    file_1 = f'data/pipeline1_build_2.json'
    # file_1 = get_build_info('9293_info.json')
    data = Cause.assign_cursor(cursor).extract(file_1, jenkins.id)
    print(data)