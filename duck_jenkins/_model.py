from duckdb import DuckDBPyConnection
from pandas.errors import EmptyDataError
from pydantic import BaseModel
from datetime import datetime
import pandas as pd
import os

from duck_jenkins._utils import json_lookup
import logging


class Base(BaseModel):
    __cursor__: DuckDBPyConnection = None
    __table_name__: str = None

    @classmethod
    def assign_cursor(cls, cursor: DuckDBPyConnection):
        cls.__cursor__ = cursor
        return cls

    @classmethod
    def get_schema(cls):
        raise NotImplementedError('Method is not being overridden')

    @classmethod
    def insert_if_not_exist(
            cls,
            sql_select: str,
            sql_insert: str
    ):
        def get_obj():
            logging.debug("SQL> ", sql_select)

            def get_result():
                result = cls.__cursor__.query(sql_select).to_df().to_dict('records')
                return cls(**result[0]) if result else None

            try:
                return get_result()
            except RuntimeError:
                cls.__cursor__.query(cls.get_schema())
                return get_result()

        obj = get_obj()
        if obj:
            return obj
        logging.debug("SQL> ", sql_insert)
        cls.__cursor__.query(sql_insert)
        obj = get_obj()
        assert obj, 'object is None'
        return obj

    @classmethod
    def select_query(cls, **kwargs):
        keys = [k for i, k in enumerate(kwargs)]
        where = ''
        if keys:
            conditions = [
                "{}={}".format(k, f"'{kwargs[k]}'" if isinstance(kwargs[k], str) else kwargs[k])
                for k in keys
            ]
            where = f"WHERE {' AND '.join(conditions)}"
        return f"SELECT * FROM {cls.__table_name__} {where}"

    @classmethod
    def select(cls, **kwargs):
        sql = cls.select_query(**kwargs)
        logging.debug("SQL> %s", sql)
        try:
            result = cls.__cursor__.query(sql).to_df().to_dict('records')
        except RuntimeError:
            cls.__cursor__.query(cls.get_schema())
            result = cls.__cursor__.query(sql).to_df().to_dict('records')
        if len(result) == 1:
            return cls(**result[0])
        return [cls(**r) for r in result]

    @classmethod
    def insert_query(cls, **kwargs):
        keys = [k for i, k in enumerate(kwargs)]
        return f"INSERT INTO {cls.__table_name__}({','.join(keys)}) VALUES({str([kwargs[k] for k in keys])[1:-1]})"

    @classmethod
    def select_insert_query(cls, **kwargs):
        return (
            cls.select_query(**kwargs),
            cls.insert_query(**kwargs)
        )


class Jenkins(Base):
    __table_name__ = 'jenkins'
    id: int
    domain_name: str

    @classmethod
    def get_schema(cls):
        return f"""
        CREATE SEQUENCE IF NOT EXISTS seq_{cls.__table_name__};
        CREATE TABLE IF NOT EXISTS {cls.__table_name__}(
            id          UINTEGER DEFAULT NEXTVAL('seq_{cls.__table_name__}'),
            domain_name VARCHAR UNIQUE,   
            PRIMARY KEY(id)
        )
        """

    @classmethod
    def factory(cls, domain_name: str):
        queries = cls.select_insert_query(domain_name=domain_name)
        return cls.insert_if_not_exist(queries[0], queries[1])


class Job(Base):
    __table_name__ = 'job'
    id: int
    name: str
    jenkins_id: int

    @classmethod
    def get_schema(cls):
        return f"""
        CREATE SEQUENCE seq_{cls.__table_name__};
        CREATE TABLE IF NOT EXISTS {cls.__table_name__}(
            id         UINTEGER DEFAULT NEXTVAL('seq_{cls.__table_name__}'),
            jenkins_id UINTEGER,
            name       VARCHAR,
            PRIMARY KEY(id)
        )
        """

    @classmethod
    def factory(cls, name: str, jenkins_id: int):
        queries = cls.select_insert_query(name=name, jenkins_id=jenkins_id)
        return cls.insert_if_not_exist(queries[0], queries[1])


class Result(Base):
    __table_name__ = 'result'
    id: int
    name: str

    @classmethod
    def get_schema(cls):
        return f"""
        CREATE TABLE IF NOT EXISTS {cls.__table_name__}(
            id   UINTEGER,
            name VARCHAR UNIQUE,
            PRIMARY KEY(id)
        );
        INSERT INTO {cls.__table_name__} VALUES
          (1, 'SUCCESS'),
          (2, 'FAILURE'),
          (3, 'ABORTED'),
          (4, 'UNSTABLE'),
          (5, 'NONE')
        """


class User(Base):
    __table_name__ = 'jenkins_user'
    id: int
    name: str
    lan_id: str

    @classmethod
    def get_schema(cls):
        return f"""
        CREATE SEQUENCE seq_{cls.__table_name__};
        CREATE TABLE {cls.__table_name__}(
            id      UINTEGER DEFAULT NEXTVAL('seq_{cls.__table_name__}'),
            lan_id VARCHAR UNIQUE,
            name    VARCHAR,
            PRIMARY KEY(id)
        )
        """

    @classmethod
    def factory(cls, name: str, lan_id: str):
        queries = cls.select_insert_query(lan_id=lan_id, name=name)
        return cls.insert_if_not_exist(queries[0], queries[1])


class Cause(Base):
    __table_name__ = 'cause'
    id: int
    category: str

    @classmethod
    def get_schema(cls):
        return f"""
        CREATE SEQUENCE seq_{cls.__table_name__};
        CREATE TABLE {cls.__table_name__}(
            id       UINTEGER DEFAULT NEXTVAL('seq_{cls.__table_name__}'),
            category VARCHAR UNIQUE,
            PRIMARY KEY(id)
        )
        """

    @classmethod
    def factory(cls, category: str):
        queries = cls.select_insert_query(category=category)
        return cls.insert_if_not_exist(queries[0], queries[1])

    @classmethod
    def extract(cls, json_file, jenkins_id: int):
        job = Job.assign_cursor(cls.__cursor__)
        cause = Cause.assign_cursor(cls.__cursor__)
        user = User.assign_cursor(cls.__cursor__)

        causes = json_lookup(json_file, '$.actions[?(@._class=="hudson.model.CauseAction")].causes')
        data = {
            'upstream_build': 0,
            'upstream_project': 0,
            'upstream_type': 0,
            'user_id': 0,
            'user_type': 0
        }

        for c in causes:
            upstream_build = c.get('upstreamBuild')
            if upstream_build:
                data['upstream_build'] = upstream_build
                data['upstream_project'] = job.factory(c['upstreamProject'], jenkins_id).id
                data['upstream_type'] = cause.factory(c['_class']).id
                continue

            user_name = c.get('userName')
            data['user_type'] = cause.factory(c['_class']).id
            if user_name:
                data['user_id'] = user.factory(user_name, c['userId']).id
                data['user_name'] = user_name

        return data


class Build(Base):
    __table_name__ = 'build'

    id: int
    job_id: int
    build_number: int
    result_id: int
    user_id: int
    trigger_type: int  # it is a cause type
    duration: int
    timestamp: datetime
    parameter_id: int = 0
    upstream_job_id: int = 0
    upstream_build_number: int = 0
    upstream_type: int = 0  # it is a cause type
    previous_build_number: int = 0

    @classmethod
    def get_schema(cls):
        return f"""
        CREATE SEQUENCE seq_{cls.__table_name__};
        CREATE TABLE {cls.__table_name__}(
            id                    UBIGINT DEFAULT NEXTVAL('seq_{cls.__table_name__}'),
            job_id                UINTEGER,
            build_number          UINTEGER,
            result_id             UINTEGER,
            user_id               UINTEGER DEFAULT(0),
            trigger_type          UINTEGER,
            duration              UINTEGER,
            timestamp             TIMESTAMP,
            upstream_job_id       UINTEGER DEFAULT(0),
            upstream_build_number UINTEGER DEFAULT(0),
            upstream_type         UINTEGER,
            previous_build_number UINTEGER DEFAULT(0),
            PRIMARY KEY(id)
        )
        """

    @classmethod
    def factory(
            cls,
            job: Job,
            build_number: int,
            result: Result,
            duration: int,
            timestamp: int,
            user_id: int,
            trigger_type: int,
            upstream_job: int,
            upstream_type: int,
            upstream_build_number: int,
            previous_build_number: int
    ):
        queries = cls.select_insert_query(
            job_id=job.id,
            build_number=build_number,
            result_id=result.id,
            user_id=user_id,
            duration=duration,
            timestamp=pd.to_datetime(timestamp, unit='ms').strftime('%Y-%m-%d %H:%M:%S'),
            upstream_job_id=upstream_job,
            upstream_build_number=upstream_build_number,
            upstream_type=upstream_type,
            previous_build_number=previous_build_number,
            trigger_type=trigger_type
        )
        return cls.insert_if_not_exist(queries[0], queries[1])

    @classmethod
    def insert(cls, json_file: str, job: Job):
        build_number = json_lookup(json_file, '$.number')
        result = json_lookup(json_file, '$.result')
        result = result if result else 'NONE'
        result_obj = Result.assign_cursor(cls.__cursor__).select(name=result)

        duration = json_lookup(json_file, '$.duration')
        timestamp = json_lookup(json_file, '$.timestamp')
        previous_build_number = json_lookup(json_file, '$.previousBuild.number')
        previous_build_number = previous_build_number if previous_build_number else 0

        causes_extracted = Cause.assign_cursor(cls.__cursor__).extract(json_file, job.jenkins_id)

        logging.info("+ Build [build_number: %s, result: (%s), duration: %s, timestamp: %s, previous_build: %s]",
                     build_number, result_obj, duration, timestamp, previous_build_number)
        logging.info("+ Cause [%s]", causes_extracted)
        return cls.factory(
            job=job,
            build_number=build_number,
            result=result_obj,
            duration=duration,
            timestamp=timestamp,
            trigger_type=causes_extracted['user_type'],
            upstream_job=causes_extracted['upstream_project'],
            user_id=causes_extracted['user_id'],
            upstream_build_number=causes_extracted['upstream_build'],
            upstream_type=causes_extracted['upstream_type'],
            previous_build_number=previous_build_number
        )


class ParameterDictionary(Base):
    __table_name__ = 'parameter_dictionary'
    id: int
    name: str

    @classmethod
    def get_schema(cls):
        return f"""
        CREATE SEQUENCE seq_{cls.__table_name__};
        CREATE TABLE {cls.__table_name__}(
            id     UBIGINT DEFAULT NEXTVAL('seq_{cls.__table_name__}'),
            name   VARCHAR UNIQUE,
            PRIMARY KEY(id)
        )
        """

    @classmethod
    def factory(cls, name: str):
        queries = cls.select_insert_query(name=name)
        return cls.insert_if_not_exist(queries[0], queries[1])


class Parameter(Base):
    __table_name__ = 'parameter'
    build_id: int
    name_id: int
    value: str

    @classmethod
    def get_schema(cls):
        return f"""
        CREATE TABLE {cls.__table_name__}(
            build_id  UBIGINT,
            name_id   UINTEGER,
            value     VARCHAR,
            PRIMARY KEY(build_id, name_id)   
        )
        """

    @classmethod
    def factory(cls, build_id: int, name_id: int, value: str):
        select = cls.select_query(
            build_id=build_id,
            name_id=name_id
        )
        insert = cls.insert_query(
            name_id=name_id,
            value=value,
            build_id=build_id
        )
        return cls.insert_if_not_exist(select, insert)

    @classmethod
    def insert(cls, json_file: str, build_id: int):
        parameters = json_lookup(json_file, '$.actions[?(@._class=="hudson.model.ParametersAction")].parameters')
        data = {0: ''}
        for p in parameters:
            name = p['name']
            value = p['value'] if p['value'] else ''
            param_dict = ParameterDictionary.assign_cursor(cls.__cursor__).factory(name)
            data[param_dict.id] = value

        for name_id in data.keys():
            cls.factory(
                build_id=build_id,
                name_id=name_id,
                value=data[name_id]
            )


class Artifact(Base):
    __table_name__ = 'artifact'
    id: int
    build_id: int
    file_name: str
    dir: str
    size: int
    timestamp: datetime

    @classmethod
    def get_schema(cls):
        return f"""
        CREATE SEQUENCE IF NOT EXISTS seq_{cls.__table_name__};
        CREATE TABLE IF NOT EXISTS {cls.__table_name__}(
            id         UBIGINT DEFAULT NEXTVAL('seq_{cls.__table_name__}'),
            build_id   UBIGINT,
            file_name  VARCHAR,
            dir        VARCHAR,
            size       UBIGINT,
            timestamp  TIMESTAMP,
            PRIMARY KEY(id)   
        )
        """

    @staticmethod
    def size_in_byte(size: str) -> int:
        x = str(size).split(' ')
        if len(x) < 2:
            return int(size)

        unit = x[1].upper()
        if unit == 'B':
            return int(x[0])
        if unit == 'KB':
            return int(float(x[0]) * 1024)
        if unit == 'MB':
            return int(float(x[0]) * 1024 ** 2)
        if unit == 'GB':
            return int(float(x[0]) * 1024 ** 3)
        if unit == 'TB':
            return int(float(x[0]) * 1024 ** 4)

        raise ValueError("Not supported unit or value: " + size)

    @classmethod
    def insert(cls, build: Build, data_dir: str):
        job = Job.assign_cursor(cls.__cursor__).select(id=build.job_id)
        jenkins = Jenkins.assign_cursor(cls.__cursor__).select(id=job.jenkins_id)

        _dir = f"{data_dir}/{jenkins.domain_name}/{job.name}/{build.build_number}_artifact.csv"
        if not os.path.exists(_dir):
            return

        if cls.select(build_id=build.id):
            logging.info(f"skipping inserted build: {build.id}")
            return
        try:
            df = pd.read_csv(_dir)
        except EmptyDataError:
            logging.info("Skipping empty content artifact: %s", _dir)
            return

        df['build_id'] = build.id
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='%b %d, %Y %I:%M:%S %p').astype(str)
        df['size'] = df['size'].apply(lambda x: cls.size_in_byte(x))
        df = df.fillna('')

        df.to_sql(
            name=cls.__table_name__,
            con=cls.__cursor__,
            if_exists='append',
            index=False,
            method='multi'
        )
