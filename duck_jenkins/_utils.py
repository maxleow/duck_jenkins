import json
from jsonpath_ng.ext import parser
import os
import logging
import requests


def json_lookup(file, jpath):
    with open(file, 'r') as json_file:
        json_data = json.load(json_file)
    values = [match.value for match in parser.parse(jpath).find(json_data)]
    if values:
        assert len(values) == 1, 'invalid data'
        return values[0]
    return values


def to_json(filename, data):
    _dir = os.path.dirname(filename)
    if not os.path.exists(_dir):
        os.makedirs(_dir)
    with open(filename, 'w') as fp:
        json.dump(data, fp)


def get_json_file(data_directory: str, domain_name: str, project_name: str, build_number: int):
    return data_directory + f'/{domain_name}/{project_name}/{build_number}_info.json'


def upstream_lookup(json_file: str):
    jpath = '$.actions[?(@._class=="hudson.model.CauseAction")].causes'
    causes = json_lookup(json_file, jpath)
    logging.info(causes)
    if causes:
        return causes[-1]
    return None


def request(domain_name: str, project_name: str, build_number: int, auth: tuple, verify_ssl: bool = True):
    logging.info(f"Pulling: {project_name} {build_number}")
    url = "https://{}/job/{}/{}/api/json".format(
        domain_name,
        project_name.replace('/', '/job/'),
        build_number
    )
    return requests.get(url, auth=auth, verify=verify_ssl)
