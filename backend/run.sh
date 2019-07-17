#!/bin/bash
export TASKCLUSTER_SECRET="project/relman/code-coverage/dev"
gunicorn --bind localhost:8000 --reload --reload-engine=poll --log-file=- code_coverage_backend.flask:app
