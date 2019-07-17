# Mozilla Code Coverage Backend


## Setup instructions for developpers

```shell
mkvirtualenv -p /usr/bin/python3 ccov-backend
cd backend/
pip install -r requirements.txt -r requirements-dev.txt 
pip install -e .
```

You should now be able to run tests and linting:

```shell
pytest 
flake8 
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
