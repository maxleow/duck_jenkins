import json
from typing import List

from jsonpath_ng.ext import parser
import os
import logging
import requests
from requests import Response


def json_lookup(file: str, jpath: str) -> List[str]:
    """
    Using JSONPath to locate data from a json file
    :param file: Json file
    :param jpath: JSONPath expression
    :return: The result
    """
    with open(file, 'r') as json_file:
        json_data = json.load(json_file)
    values = [match.value for match in parser.parse(jpath).find(json_data)]
    if values:
        assert len(values) == 1, 'invalid data'
        return values[0]
    return values


def to_json(filename: str, data: str):
    """
    Serialize JSON content into a file.

    :param filename: file name
    :param data: Content in JSON format
    :return:
    """
    _dir = os.path.dirname(filename)
    if not os.path.exists(_dir):
        os.makedirs(_dir)
    with open(filename, 'w') as fp:
        json.dump(data, fp)


def get_json_file(
        data_directory: str,
        domain_name: str,
        project_name: str,
        build_number: int
) -> str:
    """
    Generate the extracted JSON file through domain name, project name and build number
    :param data_directory: JenkinsData extracted root directory which contains all jenkins' server domain names
    :param domain_name: used to identify and construct pulling url
    :param project_name: Jenkins's Job name
    :param build_number: build number from the job
    :return: JSON file path
    """
    return data_directory + f'/{domain_name}/{project_name}/{build_number}_info.json'


def upstream_lookup(json_file: str):
    """
    Extract upstream information from a given json file
    :param json_file: json file path
    :return: the correct upstream information.
    """
    jpath = '$.actions[?(@._class=="hudson.model.CauseAction")].causes'
    causes = json_lookup(json_file, jpath)
    logging.info(causes)
    if causes:
        return causes[-1]
    return None


def request(
        domain_name: str,
        project_name: str,
        build_number: int,
        auth: tuple,
        verify_ssl: bool = True
) -> Response:
    """
    GET request to the Jenkins server to get build information through API
    :param domain_name: Target Jenkins server domain name
    :param project_name: Jenkins's Job name
    :param build_number: build number from the job.
    :param auth: (optional) Auth tuple to enable Basic/Digest/Custom HTTP Auth.
    :param verify_ssl: (optional) Either a boolean, in which case it controls whether we verify
            the server's TLS certificate, or a string, in which case it must be a path
            to a CA bundle to use. Defaults to ``True``.
    :return:
    """
    logging.info(f"Pulling: {project_name} {build_number}")
    url = "https://{}/job/{}/{}/api/json".format(
        domain_name,
        project_name.replace('/', '/job/'),
        build_number
    )
    return requests.get(url, auth=auth, verify=verify_ssl)
