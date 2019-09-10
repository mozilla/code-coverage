# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from code_coverage_backend.api import coverage_latest
from code_coverage_backend.report import Report


def test_latest(mock_cache):
    """
    Test the /v2/latest function
    """

    # Empty at first
    assert coverage_latest() == []

    # Add some reports on mozilla-central
    for rev in range(30):
        mock_cache.bucket.add_mock_blob(
            f"mozilla-central/rev{rev}/all:all.json.zstd", coverage=rev / 100.0
        )
        report = Report(
            mock_cache.reports_dir,
            "mozilla-central",
            f"rev{rev}",
            date=1000 + rev,
            push_id=rev * 5,
        )
        mock_cache.ingest_report(report)

    # And one on another repo
    mock_cache.bucket.add_mock_blob("myrepo/deadbeef/all:all.json.zstd", coverage=1)
    report = Report(mock_cache.reports_dir, "myrepo", "deadbeef", date=1000, push_id=2)
    mock_cache.ingest_report(report)

    # Check endpoint lists last 10 revisions
    assert coverage_latest() == [
        {"push": 145, "revision": "rev29"},
        {"push": 140, "revision": "rev28"},
        {"push": 135, "revision": "rev27"},
        {"push": 130, "revision": "rev26"},
        {"push": 125, "revision": "rev25"},
        {"push": 120, "revision": "rev24"},
        {"push": 115, "revision": "rev23"},
        {"push": 110, "revision": "rev22"},
        {"push": 105, "revision": "rev21"},
        {"push": 100, "revision": "rev20"},
    ]

    # Another repository does not
    assert coverage_latest("myrepo") == [{"push": 2, "revision": "deadbeef"}]
