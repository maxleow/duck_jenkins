import glob
import os.path
import re

import pandas as pd
import io
import requests
from duckdb import DuckDBPyConnection

from duck_jenkins._model import Job, Build, Parameter, Artifact, Jenkins
from duck_jenkins._utils import to_json, upstream_lookup, json_lookup


class JenkinsData:
    domain_name: str
    verify_ssl: bool = True
    auth: bool = False
    user_id: str = None
    def __init__(
            self,
            domain_name: str,
            data_directory: str = '.',
            verify_ssl: bool = True,
            user_id: str = None,
            secret: str = None,
            _skip_trial: int = 5,
    ):
        self.data_directory = os.path.abspath(data_directory + '/' + domain_name)
        self.domain_name = domain_name
        self.verify_ssl = verify_ssl
        self.__auth = None
        self.skip_trial = _skip_trial
        if user_id and secret:
            self.__auth = (user_id, secret)

    secret: str = None

    def pull_artifact(self, json_file: str, overwrite: bool = False):
        artifacts = json_lookup(json_file, '$.artifacts')
        url = json_lookup(json_file, '$.url')
        build_number = json_lookup(json_file, '$.number')
        target = os.path.dirname(json_file) + f"/{build_number}_artifact.csv"
        dirs = {os.path.dirname(a['relativePath']) for a in artifacts}

        def request():
            dfs = []
            for d in dirs:
                full_url = url + f'/artifact/{d}'
                print(full_url)
                get = requests.get(
                    full_url,
                    auth=self.__auth,
                    verify=False)

                if get.ok and get.content:
                    html = pd.read_html(io.StringIO(get.content.decode('utf-8')))
                    if html:
                        df = html[0]
                        df = df.iloc[:-1, 1:-1].dropna()
                        df['dir'] = d
                        df = df.rename(columns={1: 'file_name', 2: 'timestamp', 3: 'size'})
                        dfs.append(df)
                else:
                    continue

            if dfs:
                print('writing artifact: ', target)
                pd.concat(dfs).to_csv(target, index=False)

        if overwrite:
            request()
        elif not os.path.exists(target):
            request()
        else:
            print('skipping artifact: ', build_number)

    def pull(
            self,
            project_name: str,
            build_number: int,
            recursive_upstream: bool = False,
            recursive_previous: int = 0,
            recursive_previous_trial: int = 5,
            artifact: bool = False,
            overwrite: bool = False,
    ):
        json_file = self.data_directory + f'/{project_name}/{build_number}_info.json'
        ok = True

        def request():
            print("Pulling: ", project_name, build_number)
            url = "https://{}/job/{}/{}/api/json".format(
                self.domain_name,
                project_name.replace('/', '/job/'),
                build_number
            )
            get = requests.get(url, auth=self.__auth, verify=self.verify_ssl)
            if get.ok:
                print('writing to:', json_file)
                to_json(json_file, get.json())
            return get.ok

        if overwrite:
            ok = request()
        elif not os.path.exists(json_file):
            ok = request()
        else:
            print('skipping request: ', project_name, build_number)
            print('found at: ', json_file)
            # return

        if ok:
            if artifact:
                self.pull_artifact(json_file, overwrite=overwrite)
            if recursive_upstream:
                cause = upstream_lookup(json_file)
                if cause:
                    self.pull(
                        project_name=cause['upstreamProject'],
                        build_number=cause['upstreamBuild'],
                        recursive_upstream=recursive_upstream,
                        artifact=artifact,
                        overwrite=overwrite,
                        recursive_previous=0,
                        recursive_previous_trial=recursive_previous_trial
                    )
        if recursive_previous:
            previous_build = build_number - 1
            _trial = self.skip_trial if ok else recursive_previous_trial
            print('remaining trial:', _trial)
            if _trial > 0:
                self.pull(
                    project_name=project_name,
                    build_number=previous_build,
                    recursive_upstream=recursive_upstream,
                    recursive_previous=recursive_previous - 1,
                    recursive_previous_trial=_trial-1,
                    artifact=artifact,
                    overwrite=overwrite
                )


class DuckLoader:
    def __init__(self, cursor: DuckDBPyConnection, jenkins_data_directory: str = '.'):
        self.cursor = cursor
        self.data_directory = jenkins_data_directory

    def get_last_updated_build(self, job_name: str):
        sql = "SELECT build_number " \
              "FROM build left join job on build.job_id=job.id " \
              f"WHERE job.name='{job_name}' " \
              "order by build.build_number desc limit 1"
        return self.cursor.query(sql).fetchone()

    def import_into_db(self, jenkins_domain_name: str):
        regex = f"{jenkins_domain_name}/(.*)/.*.json"
        jenkins = Jenkins.assign_cursor(self.cursor).factory(jenkins_domain_name)

        job = Job.assign_cursor(self.cursor)
        build = Build.assign_cursor(self.cursor)
        parameter = Parameter.assign_cursor(self.cursor)
        artifact = Artifact.assign_cursor(self.cursor)

        job_paths = glob.glob(f"{jenkins_domain_name}/*")
        print(job_paths)

        def insert_build(_job: Job, _json_files: list):
            for f in _json_files:
                print('### Build ###')
                b = build.insert(f, _job)

                print('### Parameters ###')
                parameter.insert(f, b.id)

                print('### Artifacts ###')
                artifact.insert(build=b, data_dir=self.data_directory)
                print('---')

        for job_path in job_paths:
            non_feature_branch_json_files = glob.glob(job_path + "/*.json")
            if non_feature_branch_json_files:
                job_name = re.search(regex, non_feature_branch_json_files[0]).group(1)
                insert_build(job.factory(job_name, jenkins.id), non_feature_branch_json_files)
            else:
                feature_branches = glob.glob(job_path + "/*")
                for branch in feature_branches:
                    json_files = glob.glob(branch + "/*_info.json")
                    job_name = re.search(regex, json_files[0]).group(1)
                    insert_build(job.factory(job_name, jenkins.id), json_files)
