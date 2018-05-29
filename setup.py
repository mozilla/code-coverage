from setuptools import setup, find_packages

setup(
    name='firefox_code_coverage',
    version='1.0.0',
    description='Code Coverage Report generator for Firefox',
    packages=find_packages(exclude=['contrib', 'docs', 'tests'])
)
