import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="duck-jenkins",
    version="0.0.19",
    install_requires=[
        "duckdb",
        "pandas",
        "requests",
        "jsonpath-ng",
        "pydantic",
        "aiohttp"
    ],
    author="Max Leow",
    author_email="maxengiu@outlook.com",
    description="Jenkins build data ETL with DuckDB",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/maxleow/duck-jenkins",
    project_urls={
        "Bug Tracker": "https://github.com/maxleow/duck-jenkins/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],

    python_requires=">=3.7",
)
