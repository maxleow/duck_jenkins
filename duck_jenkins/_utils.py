import json
from jsonpath_ng.ext import parser
import os


def json_lookup(file, jpath):
    with open(file, 'r') as json_file:
        json_data = json.load(json_file)
    values = [match.value for match in parser.parse(jpath).find(json_data)]
    if values:
        assert len(values)==1, 'invalid data'
        return values[0]
    return values


def to_json(filename, data):
    _dir = os.path.dirname(filename)
    if not os.path.exists(_dir):
        os.makedirs(_dir)
    with open(filename, 'w') as fp:
        json.dump(data, fp)


def upstream_lookup(json_file: str):
    jpath='$.actions[?(@._class=="hudson.model.CauseAction")].causes'
    causes = json_lookup(json_file, jpath)
    for c in causes:
        upstream_build = c.get('upstreamBuild')
        if upstream_build:
            return c
    return None