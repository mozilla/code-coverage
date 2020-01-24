# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import setuptools


def read_requirements(file_):
    lines = []
    with open(file_) as f:
        for line in f.readlines():
            line = line.strip()
            if line.startswith("https://"):
                params = {
                    p[: p.index("=")]: p[p.index("=") + 1 :]
                    for p in line.split("#")[1].split("&")
                }
                line = params["egg"]
            elif line == "" or line.startswith("#") or line.startswith("-"):
                continue
            line = line.split("#")[0].strip()
            lines.append(line)
    return sorted(list(set(lines)))


with open("VERSION") as f:
    VERSION = f.read().strip()


setuptools.setup(
    name="firefox-code-coverage",
    version=VERSION,
    description="Code Coverage Report generator for Firefox",
    author="Mozilla Release Management Analysis (sallt)",
    author_email="release-mgmt-analysis@mozilla.com",
    url="https://github.com/mozilla/code-coverage",
    tests_require=read_requirements("test-requirements.txt"),
    install_requires=read_requirements("requirements.txt"),
    packages=setuptools.find_packages(),
    include_package_data=True,
    zip_safe=False,
    license="MPL2",
    entry_points={
        "console_scripts": [
            "firefox-code-coverage = firefox_code_coverage.codecoverage:main"
        ]
    },
)
