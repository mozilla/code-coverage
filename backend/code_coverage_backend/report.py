# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os

import structlog

from code_coverage_backend.hgmo import hgmo_revision_details

logger = structlog.get_logger(__name__)

DEFAULT_FILTER = "all"


class Report(object):
    """
    A single coverage report
    """

    def __init__(
        self,
        base_dir,
        repository,
        changeset,
        platform=DEFAULT_FILTER,
        suite=DEFAULT_FILTER,
        push_id=None,
        date=None,
    ):
        assert isinstance(repository, str)
        assert isinstance(changeset, str)
        self.base_dir = base_dir
        self.repository = repository
        self.changeset = changeset
        self.platform = platform
        self.suite = suite

        # Get extra information from HGMO
        if push_id or date:
            self.push_id = push_id
            self.date = date
        else:
            self.push_id, date = hgmo_revision_details(repository, changeset)
            self.date = int(date)

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def __eq__(self, other):

        return isinstance(other, Report) and (
            self.base_dir,
            self.repository,
            self.changeset,
            self.platform,
            self.suite,
        ) == (
            other.base_dir,
            other.repository,
            other.changeset,
            other.platform,
            other.suite,
        )

    @property
    def name(self):
        return "{}/{}/{}:{}".format(
            self.repository, self.changeset, self.platform, self.suite
        )

    @property
    def path(self):
        """Local path on FS, decompressed"""
        return os.path.join(self.base_dir, f"{self.name}.json")

    @property
    def archive_path(self):
        """Local path on FS, compressed"""
        return f"{self.path}.zstd"

    @property
    def gcp_path(self):
        """Remote path on GCP storage"""
        return f"{self.name}.json.zstd"

    @property
    def key_overall(self):
        """Redis key to store the overall coverage data for this report"""
        platform = self.platform or "all"
        suite = self.suite or "all"
        return f"overall:{self.repository}:{self.changeset}:{platform}:{suite}"
