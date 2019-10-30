#!/bin/bash -e

pip install --disable-pip-version-check --no-cache-dir --quiet -r test-requirements.txt

python -m unittest discover tests
python setup.py sdist bdist_wheel
pip install dist/firefox_code_coverage-1.0.0.tar.gz
