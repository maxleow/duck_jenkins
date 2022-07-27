import glob
import os.path
import re
from typing import Tuple, Optional, Any, Coroutine

import pandas as pd
from aiohttp import ClientSession, BasicAuth

from duckdb import DuckDBPyConnection

from duck_jenkins._model import Job, Build, Parameter, Artifact, Jenkins
from duck_jenkins._utils import to_json, upstream_lookup, json_lookup, request, get_json_file
import logging
import time
import asyncio
import aiohttp


class JenkinsData:

    def __init__(
            self,
            domain_name: str,
            data_directory: str = '.',
            verify_ssl: bool = True,
            user_id: str = None,
            secret: str = None,
    ):
        self.data_directory = data_directory
        self.domain_name = domain_name
        self.verify_ssl = verify_ssl
        self.__auth = None
        if user_id and secret:
            self.__auth = (user_id, secret)

    def pull_upstream(
            self,
            project_name: str,
            build_number: int,
            overwrite: bool = False,
            artifact: bool = False,
            recursive: bool = False
    ):
        json_file = get_json_file(self.data_directory, self.domain_name, project_name, build_number)
        logging.info("Pulling upstream, file[%s]: %s", json_file, os.path.exists(json_file))

        if not os.path.exists(json_file):
            raise FileNotFoundError(json_file)

        while True:
            cause = upstream_lookup(json_file)
            if cause and cause.get('upstreamProject') and cause.get('upstreamBuild'):
                logging.info("Found upstream build: %s %s", cause['upstreamProject'], cause['upstreamBuild'])
                files = self.pull(
                    project_name=cause['upstreamProject'],
                    build_number=cause['upstreamBuild'],
                    overwrite=overwrite,
                    artifact=artifact
                )
                if not recursive or not files[0]:
                    break
                json_file = files[0]
            else:
                logging.info("No upstream build: %s %s", project_name, build_number)
                break

    def pull_previous(
            self,
            project_name: str,
            build_number: int,
            overwrite: bool,
            artifact: bool,
            trial=5,
            size=0,
    ):
        previous_build = build_number - 1
        counter = 1
        while True:
            if previous_build == 0:
                break
            files = self.pull(
                project_name=project_name,
                build_number=previous_build,
                overwrite=overwrite,
                artifact=artifact
            )
            if not files[0]:
                trial -= 1
                logging.info('Build exist with remaining trial: %s', trial)
                if trial == 0:
                    break
            previous_build -= 1
            counter += 1
            if size < counter:
                break

    @classmethod
    async def _pull_artifact(
            cls,
            domain_name: str,
            auth: tuple,
            verify_ssl: bool,
            project_name: str,
            build_number: int,
            data_directory: str,
            overwrite: bool = False
    ) -> str:
        data_directory = os.path.abspath(data_directory + '/' + domain_name)
        json_file = get_json_file(data_directory, domain_name, project_name, build_number)

        if not os.path.exists(json_file):
            raise FileNotFoundError(f"file: [{json_file}] not found")

        artifacts = json_lookup(json_file, '$.artifacts')
        logging.info('Artifacts size: %s', len(artifacts))
        url = json_lookup(json_file, '$.url')
        build_number = json_lookup(json_file, '$.number')
        target = os.path.dirname(json_file) + f"/{build_number}_artifact.csv"
        dirs = {os.path.dirname(a['relativePath']) for a in artifacts}

        async def get_artifacts(session: ClientSession, artifact_url: str, dir_name: str) -> pd.DataFrame:
            async with session.get(
                    artifact_url, ssl=verify_ssl,
                    auth=BasicAuth(auth[0], auth[1])) as resp:
                html = await resp.text()
                logging.info(artifact_url)
                logging.info('downloaded content: %s', len(html))
                try:
                    dfs = pd.read_html(html)
                    if dfs:
                        df = dfs[0]
                        df = df.iloc[:-1, 1:-1].dropna()
                        df['dir'] = dir_name
                        df = df.rename(columns={1: 'file_name', 2: 'timestamp', 3: 'size'})
                        return df
                    return pd.DataFrame([])
                except ValueError:
                    return pd.DataFrame([])

        async def fetch(artifact_url):
            async with aiohttp.ClientSession() as session:
                tasks = []
                for d in dirs:
                    full_url = artifact_url + f'/artifact/{d}'
                    tasks.append(asyncio.ensure_future(get_artifacts(session, full_url, d)))

                dfs = await asyncio.gather(*tasks)
                if dfs:
                    pd.concat(dfs).to_csv(target, index=False)

        if overwrite or not os.path.exists(target):
            await fetch(url)
        else:
            logging.info('skipping existing artifact for build: %s', build_number)

        return target

    @classmethod
    def _pull(
            cls,
            domain_name: str,
            auth: tuple,
            verify_ssl: bool,
            project_name: str,
            build_number: int,
            data_directory: str,
            artifact: bool = False,
            overwrite: bool = False
    ) -> Tuple[Any, Optional[Coroutine[Any, Any, str]]]:
        json_file = get_json_file(
            data_directory,
            domain_name,
            project_name,
            build_number
        )
        artifact_file = None
        if overwrite or not os.path.exists(json_file):
            get = request(
                domain_name=domain_name,
                project_name=project_name,
                build_number=build_number,
                auth=auth,
                verify_ssl=verify_ssl,

            )
            if get.ok:
                to_json(json_file, get.json())
            else:
                json_file = None

        if artifact:
            artifact_file = cls._pull_artifact(
                domain_name=domain_name,
                auth=auth,
                verify_ssl=verify_ssl,
                project_name=project_name,
                build_number=build_number,
                data_directory=data_directory
            )
        return json_file, artifact_file

    def pull(
            self,
            project_name: str,
            build_number: int,
            artifact: bool = False,
            overwrite: bool = False,
    ):
        json_file = get_json_file(self.data_directory, self.domain_name, project_name, build_number)
        logging.info('Overwrite: %s', overwrite)
        logging.info('Json file exist: %s, %s, %s', os.path.exists(json_file), project_name, build_number)

        return JenkinsData._pull(
            domain_name=self.domain_name,
            auth=self.__auth,
            verify_ssl=self.verify_ssl,
            project_name=project_name,
            build_number=build_number,
            data_directory=self.data_directory,
            artifact=artifact,
            overwrite=overwrite
        )


class DuckLoader:
    def __init__(self, cursor: DuckDBPyConnection, jenkins_data_directory: str = '.'):
        self.cursor = cursor
        self.data_directory = jenkins_data_directory

    @staticmethod
    def insert_build(
            job_dir: str,
            jenkins_domain_name: str,
            data_dir: str,
            cursor: DuckDBPyConnection,
            overwrite: bool = False
    ):
        regex = f"{jenkins_domain_name}/(.*)/(.*)_info.json"
        file_names = glob.glob(job_dir + "/*.json")
        file_names.sort()
        for file_name in file_names:
            job_name = re.search(regex, file_name).group(1)
            build_number = re.search(regex, file_name).group(2)
            jenkins = Jenkins.assign_cursor(cursor).factory(jenkins_domain_name)
            job = Job.assign_cursor(cursor).factory(job_name, jenkins.id)
            build = Build.assign_cursor(cursor).select(build_number=build_number, job_id=job.id)
            logging.info(f"inserting [job_name: {job_name}, build_number: {build_number}]")
            if not overwrite and build:
                logging.info(f'skipping existing build: {build.id}')
                continue
            if overwrite or not build:
                st = time.time()
                b = Build.assign_cursor(cursor).insert(file_name, job)
                logging.debug(f"Execution time: {time.time() - st}s")

                st = time.time()
                Parameter.assign_cursor(cursor).insert(file_name, b.id)
                logging.debug(f"Execution time: {time.time() - st}s")

                st = time.time()
                Artifact.assign_cursor(cursor).insert(build=b, data_dir=data_dir)
                logging.debug(f"Execution time: {time.time() - st}s")
                logging.info('---')

    def import_into_db(self, jenkins_domain_name: str, overwrite: bool = False):

        job_paths = glob.glob(f"{self.data_directory}/{jenkins_domain_name}/*")
        logging.debug(job_paths)

        for job_path in job_paths:
            job_dir = glob.glob(job_path + "/*.json")
            if not job_dir:
                job_dirs = glob.glob(job_path + "/*")
                for job_dir in job_dirs:
                    DuckLoader.insert_build(
                        job_dir=job_dir,
                        jenkins_domain_name=jenkins_domain_name,
                        data_dir=self.data_directory,
                        cursor=self.cursor,
                        overwrite=overwrite
                    )
            else:
                DuckLoader.insert_build(
                    job_dir=job_path,
                    jenkins_domain_name=jenkins_domain_name,
                    data_dir=self.data_directory,
                    cursor=self.cursor,
                    overwrite=overwrite
                )
