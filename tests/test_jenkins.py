import glob

import responses
import json
import os


URL = "https://{}/job/{}/{}/api/json"
FEATURE_BRANCH_PROJECT = 'pipeline2/master'
PROJECT_NAME = FEATURE_BRANCH_PROJECT.replace('/', '/job/')

def get_build_info(file_name: str):
    file_name = os.path.abspath('.') + f'/tests/data/{file_name}'
    with open(file_name) as jf:
        return json.load(jf)


@responses.activate
def test_pull_with_recursive_upstream(jenkins_data):


    responses.add(
        responses.GET,
        URL.format(jenkins_data.domain_name, PROJECT_NAME, 2),
        json=get_build_info('pipeline1_build_2.json')
    )

    responses.add(
        responses.GET,
        URL.format(jenkins_data.domain_name, PROJECT_NAME, 1),
        json=get_build_info('pipeline1_build_1.json')
    )

    jenkins_data.pull(
        project_name=FEATURE_BRANCH_PROJECT,
        build_number=2,
        recursive_upstream=True,
        recursive_previous=0,
        artifact=False,
        overwrite=True
    )
    _dir = f"{jenkins_data.data_directory}/{FEATURE_BRANCH_PROJECT}"
    assert os.path.exists(f"{_dir}/1_info.json")
    assert os.path.exists(f"{_dir}/2_info.json")
    assert len(glob.glob(f"{_dir}/*")) == 2


@responses.activate
def test_pull_without_recursive_upstream(jenkins_data):
    responses.add(
        responses.GET,
        URL.format(jenkins_data.domain_name, PROJECT_NAME, 2),
        json=get_build_info('pipeline1_build_2.json')
    )
    jenkins_data.pull(
        project_name=FEATURE_BRANCH_PROJECT,
        build_number=2,
        recursive_upstream=False,
        recursive_previous=0,
        artifact=False,
        overwrite=True
    )
    _dir = f"{jenkins_data.data_directory}/{FEATURE_BRANCH_PROJECT}"
    assert len(glob.glob(f"{_dir}/*")) == 1
    assert os.path.exists(f"{_dir}/2_info.json")


@responses.activate
def test_pull_with_recursive_upstream_and_artifact():
    pass
