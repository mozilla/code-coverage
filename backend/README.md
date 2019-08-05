# Mozilla Code Coverage Backend

This project is a Python 3 REST API, powered by [Flask](https://palletsprojects.com/p/flask/) that serves code coverage data aggregated by the bot project.

The production instance of this service is hosted on https://api.coverage.moz.tools

We currently have several endpoints implemented:

* `/v2/extensions` lists all the file extensions supported by the code coverage suite,
* `/v2/latest` lists the 10 latest code coverage reports ingested on the backend and available to query,
* `/v2/history` shows the code coverage progression for a specific path in a repository,
* `/v2/path` provides the code coverage information for a directory or file in a repository, at a given revision.


## Setup instructions for developers

```shell
mkvirtualenv -p /usr/bin/python3 ccov-backend
cd backend/
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
```

You should now be able to run tests and linting:

```shell
pre-commit run -a
```

## Run a redis instance through docker

```shell
docker run -v /tmp/ccov-redis:/data -p 6379:6379 redis
```

## Run the webserver

The development webserver will run on **http://localhost:8000**

Using default secret `project-relman/code-coverage/dev`:

```shell
./run.sh
```

You can specify any other secret as:

```shell
TASKCLUSTER_SECRET=path/to/secret ./run.sh
```
