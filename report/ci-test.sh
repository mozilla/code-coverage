#!/bin/bash -e

pip install --disable-pip-version-check --no-cache-dir --quiet -r test-requirements.txt

python -m unittest discover tests
python setup.py sdist bdist_wheel
VERSION=$(cat VERSION)
pip install dist/firefox-code-coverage-$VERSION.tar.gz
