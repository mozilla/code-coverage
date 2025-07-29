#!/bin/bash -e

pip install --disable-pip-version-check --no-cache-dir --quiet -r test-requirements.txt -r requirements.txt .

python -m unittest discover tests
python setup.py sdist bdist_wheel
VERSION=$(cat VERSION)
pip install dist/firefox_code_coverage-$VERSION.tar.gz
