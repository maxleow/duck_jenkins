# Duck Jenkins: loading jenkins build info into DuckDB
[![Python package][gh-action-python-package-badge]][gh-action-python-package]
[![PyPI][pypi-latest-release-badge]][pypi]
[![Downloads][pepy-downloads-badge]][pepy-downloads-link]
[![PyPI - Python Version][pypi-python-versions-badge]][pypi]
[![License][license-badge]][license-link]

## What is it?

ETL(Extract Transform Load) for Jenkins data.

## Installation

```shell
pip install duck-jenkins
```

## Main features

### Jenkins build extractor
  - Extract and serialize Jenkins' build information along with artefact metadata into files.
  - A fix file structure can support multiple Jenkins servers.
  - Support multi-branch structure
```text
└── data
    ├── jenkins1.example.io
    └── jenkins2.example.io
        ├── pipeline1
        │    └── 1_info.json
        └── pipeline2
            └── master
                ├── 1_info.json
                └── 1_artifact.csv
```
### DuckDB transformer
Transform all serialized data above to relational database, [DuckDB](https://duckdb.org/).

#### Database ER diagram
```mermaid
erDiagram
    Jenkins ||--o{ Job: has
    Job ||--o{ Build: has
    Build ||--o{ Artifact: has
    Build ||--o| Jenkins_User: has
    Build ||--o{ Cause: has
    Build ||--o{ Parameter: has
    Build ||--|| Result: has
    Parameter ||--|| ParameterDictionary: has
    Jenkins{
        int id PK
        str domain_name
    }
    Job{
        int id  PK
        str name
        int jenkins_id FK
    }
    Result{
        int id PK
        str name
    }
    Jenkins_User{
        int id PK
        str name
        str lan_id
    }
    Cause{
        int id PK
        str category
    }
    Build{
        int id               PK
        int job_id           FK
        int build_number
        int result_id        FK
        int user_id          FK 
        int trigger_type     FK "Cause table's PK"
        int duration
        datetime timestamp
        int upstream_job_id FK
        int upstream_build_number
        int upstream_type   FK "Cause table's PK"
        int previous_build_number
    }
    ParameterDictionary{
        int id PK
        str name
    }
    Parameter{
        int build_id FK
        int name_id  FK
        str value
    }
    Artifact{
        int id        PK
        int build_id  FK
        str file_name
        str dir
        int size
        datetime timestamp
    }
```

## Example
### Jenkins Build extractor
Following examples try to emulate the file structure aboved.

#### 1. Extract build
Extracting a multi-branch pipeline
```python
from duck_jenkins import JenkinsData

jd = JenkinsData(
    domain_name='jenkins1.example.io',
    verify_ssl=False,
    user_id='C001',
    secret='elwerqoqiweucv',
    data_directory='data'
)
jd.pull(
    project_name='pipeline2/master',
    build_number=1,
    artifact=True
)
```
---

#### 2. Extract upstream build
Let assume the upstream of `pipeline2/master/1` is `pipeline1/1`.
```python
from duck_jenkins import JenkinsData

jd = JenkinsData(
    domain_name='jenkins1.example.io',
    verify_ssl=False,
    user_id='C001',
    secret='elwerqoqiweucv',
    data_directory='data'
)
jd.pull_upstream(
    project_name='pipeline2/master',
    build_number=1,
    artifact=False
)
```
---
#### 3. Extract previous build
```python
from duck_jenkins import JenkinsData

jd = JenkinsData(
    domain_name='jenkins1.example.io',
    verify_ssl=False,
    user_id='C001',
    secret='elwerqoqiweucv',
    data_directory='data'
)
jd.pull_previous(
    project_name='pipeline2/master',
    build_number=2,  # build 2 is excluded from the extraction in this function. 
    artifact=True,
    overwrite=True,
    size=1  # say, you only interested 1 previous build.
)
```
---
### DuckDB transformation
Without transform into a database, it is useless. Following steps demostrate how to import into DuckDB.
```python
from duck_jenkins import DuckLoader
import duckdb

db = duckdb.connect('1.ddb')
cursor = db.cursor()

dl = DuckLoader(cursor, 'data')
dl.import_into_db(
    jenkins_domain_name='jenkins1.example.io', 
    overwrite=False  # False to skip insert for existing record.
)

cursor.commit()
cursor.close()
```
For more usage of `DuckDB`, visit the official document:
https://duckdb.org/docs/


[gh-action-python-package]: https://github.com/maxleow/duck_jenkins/actions/workflows/python-package.yml
[gh-action-python-package-badge]: https://github.com/maxleow/duck_jenkins/actions/workflows/python-package.yml/badge.svg
[license-badge]: https://img.shields.io/badge/License-MIT-blue.svg
[license-link]: https://github.com/maxleow/duck_jenkins/blob/main/LICENSE
[pypi]: https://pypi.org/project/duck-jenkins/
[pypi-latest-release-badge]: https://img.shields.io/pypi/v/duck-jenkins?color=blue&label=pypi&logo=version
[pypi-python-versions-badge]: https://img.shields.io/pypi/pyversions/duck-jenkins.svg
[pepy-downloads-badge]: https://static.pepy.tech/personalized-badge/duck-jenkins?period=total&units=international_system&left_color=gray&right_color=blue&left_text=Downloads
[pepy-downloads-link]: https://pepy.tech/project/duck-jenkins
