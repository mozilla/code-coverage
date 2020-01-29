#!/bin/sh -xe
DIR="$( cd "$( dirname "$0" )" && pwd )"
PIP_SETUP=/tmp/get-pip.py
VENV=/tmp/ccov-env

# Build new Python 3 virtual environment
pip install https://github.com/pypa/virtualenv/archive/16.7.9.tar.gz
virtualenv -p /usr/local/bin/python3 --no-wheel --no-pip --no-setuptools $VENV

# Run following commands in new virtualenv
. $VENV/bin/activate

# Setup pip in the new env
wget https://bootstrap.pypa.io/get-pip.py -O $PIP_SETUP
python $PIP_SETUP
rm $PIP_SETUP

# Install code coverage report
pip install -r ${DIR}/requirements.txt
pip install -e ${DIR}

# Finally run code coverage report
firefox-code-coverage
