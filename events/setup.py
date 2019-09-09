# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os.path

import setuptools

here = os.path.dirname(__file__)


def read_requirements(file_):
    with open(os.path.join(here, file_)) as f:
        return sorted(list(set(line.split("#")[0].strip() for line in f)))


with open(os.path.join(here, "VERSION")) as f:
    VERSION = f.read().strip()


setuptools.setup(
    name="code_coverage_events",
    version=VERSION,
    description="Listens to a pulse queue and trigger code coverage tasks",
    author="Mozilla Release Management",
    author_email="release-mgmt-analysis@mozilla.com",
    url="https://github.com/mozilla/code-coverage",
    tests_require=read_requirements("requirements-dev.txt"),
    install_requires=read_requirements("requirements.txt"),
    packages=setuptools.find_packages(),
    include_package_data=True,
    zip_safe=False,
    license="MPL2",
    entry_points={
        "console_scripts": ["code-coverage-events = code_coverage_events.cli:main"]
    },
)
