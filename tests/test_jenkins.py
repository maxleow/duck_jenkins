import glob

import pytest
import responses
import os

import logging

from tests.conftest import get_build_info

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.info("test")


URL = "https://{}/job/{}/{}/api/json"
FEATURE_BRANCH_PROJECT = 'pipeline2/master'
PROJECT_NAME = FEATURE_BRANCH_PROJECT.replace('/', '/job/')

def init_responses(domain_name: str):
    responses.add(
        responses.GET,
        URL.format(domain_name, PROJECT_NAME, 3),
        json=get_build_info('pipeline1_build_3.json')
    )

    responses.add(
        responses.GET,
        URL.format(domain_name, PROJECT_NAME, 2),
        json=get_build_info('pipeline1_build_2.json')
    )

    responses.add(
        responses.GET,
        URL.format(domain_name, PROJECT_NAME, 1),
        json=get_build_info('pipeline1_build_1.json')
    )


@responses.activate
@pytest.mark.parametrize("overwrite", [False,True])
def test_pull_with_recursive_upstream(jenkins_data, overwrite):

    init_responses(jenkins_data.domain_name)

    jenkins_data.pull(
        project_name=FEATURE_BRANCH_PROJECT,
        build_number=2,
        artifact=False,
        overwrite=overwrite
    )

    jenkins_data.pull_upstream(
        project_name=FEATURE_BRANCH_PROJECT,
        build_number=2,
        artifact=False,
        overwrite=overwrite,
        recursive=True
    )

    _dir = f"{jenkins_data.data_directory}/{jenkins_data.domain_name}/{FEATURE_BRANCH_PROJECT}"
    assert os.path.exists(f"{_dir}/1_info.json")
    assert os.path.exists(f"{_dir}/2_info.json")
    assert len(glob.glob(f"{_dir}/*")) == 2


@responses.activate
@pytest.mark.parametrize("overwrite", [False,True])
def test_pull_with_recursive_upstream_rebuild(jenkins_data, overwrite):

    init_responses(jenkins_data.domain_name)
    jenkins_data.pull(
        project_name=FEATURE_BRANCH_PROJECT,
        build_number=3,
        artifact=False,
        overwrite=overwrite
    )

    jenkins_data.pull_upstream(
        project_name=FEATURE_BRANCH_PROJECT,
        build_number=3,
        artifact=False,
        overwrite=overwrite,
        recursive=True
    )

    _dir = f"{jenkins_data.data_directory}/{jenkins_data.domain_name}/{FEATURE_BRANCH_PROJECT}"
    assert os.path.exists(f"{_dir}/3_info.json")
    assert os.path.exists(f"{_dir}/2_info.json")
    assert os.path.exists(f"{_dir}/1_info.json")
    assert len(glob.glob(f"{_dir}/*")) == 3


@responses.activate
def test_pull_without_recursive_upstream(jenkins_data):
    init_responses(jenkins_data.domain_name)
    jenkins_data.pull(
        project_name=FEATURE_BRANCH_PROJECT,
        build_number=2,
        artifact=False,
        overwrite=True
    )
    _dir = f"{jenkins_data.data_directory}/{jenkins_data.domain_name}/{FEATURE_BRANCH_PROJECT}"
    assert len(glob.glob(f"{_dir}/*")) == 1
    assert os.path.exists(f"{_dir}/2_info.json")


@responses.activate
@pytest.mark.parametrize("trial", [2,3,5])
def test_pull_previous_build_trial(jenkins_data, trial):

    for i in range(trial):
        responses.add(
            responses.GET,
            URL.format(jenkins_data.domain_name, PROJECT_NAME, i),
            status=404
        )

    jenkins_data.pull_previous(
        project_name=FEATURE_BRANCH_PROJECT,
        build_number=trial,
        overwrite=True,
        artifact=False,
        trial=trial
    )

@responses.activate
def test_pull_previous_build(jenkins_data):

    init_responses(jenkins_data.domain_name)

    jenkins_data.pull_previous(
        project_name=FEATURE_BRANCH_PROJECT,
        build_number=4,
        overwrite=True,
        artifact=False,
        trial=0,
        size=3
    )
    _dir = f"{jenkins_data.data_directory}/{jenkins_data.domain_name}/{FEATURE_BRANCH_PROJECT}"
    assert os.path.exists(f"{_dir}/3_info.json")
    assert os.path.exists(f"{_dir}/2_info.json")
    assert os.path.exists(f"{_dir}/1_info.json")
    assert len(glob.glob(f"{_dir}/*")) == 3

@responses.activate
@pytest.mark.parametrize("size", [1,2,3])
def test_pull_previous_build_size(jenkins_data, size):

    init_responses(jenkins_data.domain_name)

    jenkins_data.pull_previous(
        project_name=FEATURE_BRANCH_PROJECT,
        build_number=4,
        overwrite=True,
        artifact=False,
        trial=0,
        size=size
    )
    _dir = f"{jenkins_data.data_directory}/{jenkins_data.domain_name}/{FEATURE_BRANCH_PROJECT}"
    assert len(glob.glob(f"{_dir}/*")) == size