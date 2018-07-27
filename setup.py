# -*- coding: utf-8 -*-

from setuptools import find_packages
from setuptools import setup

setup(
    name='firefox_code_coverage',
    version='1.0.0',
    description='Code Coverage Report generator for Firefox',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    license='MPL2',
)
