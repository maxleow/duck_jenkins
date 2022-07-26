import responses
import duckdb
from duck_jenkins._model import Cause, Jenkins

@responses.activate
def test_cause():
    db = duckdb.connect()
    cursor = db.cursor()
    jenkins = Jenkins.assign_cursor(cursor).factory('jenkins.testing.io')
    file_1 = f'data/pipeline1_build_2.json'
    data = Cause.assign_cursor(cursor).extract(file_1, jenkins.id)
    assert data == {
        'upstream_build': 1,
        'upstream_project': 1,
        'upstream_type': 1,
        'user_id': 0,
        'user_type': 0
    }
