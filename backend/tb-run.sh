#!/bin/bash
if [[ ! $TASKCLUSTER_SECRET ]]; then
  export TASKCLUSTER_SECRET="project/relman/code-coverage/dev"
  echo 'Using dev secret'
fi
gunicorn --bind 0.0.0.0:8080 --reload --reload-engine=poll --log-file=- code_coverage_backend.flask:app
