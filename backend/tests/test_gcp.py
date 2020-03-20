# -*- coding: utf-8 -*-
import hashlib
import json
import os
import uuid

import pytest

from code_coverage_backend.report import Report


def test_download_report(mock_cache):
    """
    Test base method to download a report & store it on local FS
    """
    mock_cache.bucket.add_mock_blob("myrepo/deadbeef123/all:all.json.zstd")

    # Does not exist
    report = Report(mock_cache.reports_dir, "myrepo", "missing", date=1, push_id=1)
    assert mock_cache.download_report(report) is False

    archive = os.path.join(
        mock_cache.reports_dir, "myrepo", "deadbeef123", "all:all.json.zstd"
    )
    payload = os.path.join(
        mock_cache.reports_dir, "myrepo", "deadbeef123", "all:all.json"
    )
    assert not os.path.exists(archive)
    assert not os.path.exists(payload)

    # Valid blob
    report = Report(mock_cache.reports_dir, "myrepo", "deadbeef123", date=1, push_id=1)
    assert mock_cache.download_report(report) is True
    assert archive == report.archive_path
    assert payload == report.path

    # Only the payload remains after download
    assert not os.path.exists(archive)
    assert os.path.exists(payload)

    assert json.load(open(payload)) == {"children": {}, "coveragePercent": 0.0}

    assert mock_cache.redis.keys("*") == []


def test_ingestion(mock_cache):
    """
    Test ingestion of several reports and their retrieval through Redis index
    """
    # Setup blobs
    mock_cache.bucket.add_mock_blob("myrepo/rev1/all:all.json.zstd", coverage=0.1)
    mock_cache.bucket.add_mock_blob("myrepo/rev2/all:all.json.zstd", coverage=0.2)
    mock_cache.bucket.add_mock_blob("myrepo/rev10/all:all.json.zstd", coverage=1.0)

    # No reports at first
    assert mock_cache.redis.zcard(b"reports:myrepo") == 0
    assert mock_cache.redis.zcard(b"history:myrepo") == 0
    assert mock_cache.list_reports("myrepo") == []

    # Ingest those 3 reports
    report_1 = Report(mock_cache.reports_dir, "myrepo", "rev1", date=1000, push_id=1)
    report_2 = Report(mock_cache.reports_dir, "myrepo", "rev2", date=2000, push_id=2)
    report_10 = Report(mock_cache.reports_dir, "myrepo", "rev10", date=9000, push_id=10)
    mock_cache.ingest_report(report_1)
    mock_cache.ingest_report(report_2)
    mock_cache.ingest_report(report_10)

    # Check expiry
    assert report_1.ttl is None
    assert mock_cache.redis.ttl(report_1.key_overall) == -1

    # They must be in redis and on the file system
    assert mock_cache.redis.zcard(b"reports:myrepo:all:all") == 3
    assert mock_cache.redis.zcard(b"history:myrepo") == 3
    assert os.path.exists(
        os.path.join(mock_cache.reports_dir, "myrepo", "rev1", "all:all.json")
    )
    assert os.path.exists(
        os.path.join(mock_cache.reports_dir, "myrepo", "rev2", "all:all.json")
    )
    assert os.path.exists(
        os.path.join(mock_cache.reports_dir, "myrepo", "rev10", "all:all.json")
    )

    # Reports are exposed, and sorted by push
    assert mock_cache.list_reports("another") == []
    assert mock_cache.list_reports("myrepo") == [report_10, report_2, report_1]
    assert mock_cache.find_report("myrepo") == report_10
    assert mock_cache.get_history("myrepo", start=200, end=20000) == [
        {"changeset": "rev10", "coverage": 1.0, "date": 9000},
        {"changeset": "rev2", "coverage": 0.2, "date": 2000},
        {"changeset": "rev1", "coverage": 0.1, "date": 1000},
    ]

    # Even if we add a smaller one later on, reports are still sorted
    mock_cache.bucket.add_mock_blob("myrepo/rev5/all:all.json.zstd", coverage=0.5)
    report_5 = Report(mock_cache.reports_dir, "myrepo", "rev5", date=5000, push_id=5)
    mock_cache.ingest_report(report_5)
    assert mock_cache.list_reports("myrepo") == [
        report_10,
        report_5,
        report_2,
        report_1,
    ]
    assert mock_cache.find_report("myrepo") == report_10
    assert mock_cache.find_report("myrepo", push_range=(7, 0)) == report_5
    assert mock_cache.get_history("myrepo", start=200, end=20000) == [
        {"changeset": "rev10", "coverage": 1.0, "date": 9000},
        {"changeset": "rev5", "coverage": 0.5, "date": 5000},
        {"changeset": "rev2", "coverage": 0.2, "date": 2000},
        {"changeset": "rev1", "coverage": 0.1, "date": 1000},
    ]


def test_expiry(mock_cache):
    """
    Test expiry for platform & suite reports
    """
    mock_cache.bucket.add_mock_blob("myrepo/rev1/all:somesuite.json.zstd", coverage=1.0)
    report_suite = Report(
        mock_cache.reports_dir,
        "myrepo",
        "rev1",
        platform="all",
        suite="somesuite",
        date=1000,
        push_id=1,
    )
    mock_cache.ingest_report(report_suite)
    assert report_suite.ttl == 1296000
    assert mock_cache.redis.ttl(report_suite.key_overall) > 0

    mock_cache.bucket.add_mock_blob("myrepo/rev1/win:all.json.zstd", coverage=1.0)
    report_platform = Report(
        mock_cache.reports_dir, "myrepo", "rev1", platform="win", date=2000, push_id=2
    )
    mock_cache.ingest_report(report_platform)
    assert report_platform.ttl == 1296000
    assert mock_cache.redis.ttl(report_platform.key_overall) > 0


def test_ingest_hgmo(mock_cache, mock_hgmo):
    """
    Test ingestion using a mock HGMO
    """

    # Add a report on push 995
    rev = hashlib.md5(b"995").hexdigest()
    mock_cache.bucket.add_mock_blob(
        "myrepo/{}/all:all.json.zstd".format(rev), coverage=0.5
    )

    # Ingest last pushes
    assert mock_cache.list_reports("myrepo") == []
    assert len(mock_cache.redis.keys("changeset:myrepo:*")) == 0
    mock_cache.ingest_pushes("myrepo", "all", "all")
    assert len(mock_cache.redis.keys("changeset:myrepo:*")) > 0
    assert mock_cache.list_reports("myrepo") == [
        Report(mock_cache.reports_dir, "myrepo", rev, push_id=1, date=995)
    ]


def test_closest_report(mock_cache, mock_hgmo):
    """
    Test algo to find the closest report for any changeset
    """
    # Build revision for push 992
    revision = "992{}".format(uuid.uuid4().hex[3:])

    # No data at first
    assert mock_cache.redis.zcard("reports") == 0
    assert len(mock_cache.redis.keys("changeset:myrepo:*")) == 0

    # Try to find a report, but none is available
    with pytest.raises(Exception) as e:
        mock_cache.find_closest_report("myrepo", revision)
    assert str(e.value) == "No report found"

    # Some pushes were ingested though
    assert len(mock_cache.redis.keys("changeset:myrepo:*")) > 0

    # Add a report on 994, 2 pushes after our revision
    report_rev = hashlib.md5(b"994").hexdigest()
    mock_cache.bucket.add_mock_blob(
        "myrepo/{}/all:all.json.zstd".format(report_rev), coverage=0.5
    )
    report_994 = Report(
        mock_cache.reports_dir, "myrepo", report_rev, push_id=1, date=994
    )

    # Add a report on 990, 2 pushes before our revision
    base_rev = hashlib.md5(b"990").hexdigest()
    mock_cache.bucket.add_mock_blob(
        "myrepo/{}/all:all.json.zstd".format(base_rev), coverage=0.4
    )
    report_990 = Report(mock_cache.reports_dir, "myrepo", base_rev, push_id=1, date=990)

    # Now we have a report !
    assert mock_cache.list_reports("myrepo") == []
    assert mock_cache.find_closest_report("myrepo", revision) == report_994
    assert mock_cache.list_reports("myrepo") == [report_994]

    # This should also work for revisions before
    revision = "991{}".format(uuid.uuid4().hex[3:])
    assert mock_cache.find_closest_report("myrepo", revision) == report_994

    # ... and the revision on the push itself
    revision = "994{}".format(uuid.uuid4().hex[3:])
    assert mock_cache.find_closest_report("myrepo", revision) == report_994

    # We can also retrieve the base revision
    revision = "990{}".format(uuid.uuid4().hex[3:])
    assert mock_cache.find_closest_report("myrepo", revision) == report_990
    revision = "989{}".format(uuid.uuid4().hex[3:])
    assert mock_cache.find_closest_report("myrepo", revision) == report_990
    assert mock_cache.list_reports("myrepo") == [report_994, report_990]

    # But not for revisions after the push
    revision = "995{}".format(uuid.uuid4().hex[3:])
    with pytest.raises(Exception) as e:
        mock_cache.find_closest_report("myrepo", revision)
    assert str(e.value) == "No report found"


def test_get_coverage(mock_cache):
    """
    Test coverage access with re-download
    """
    # No report at first
    report = Report(mock_cache.reports_dir, "myrepo", "myhash", push_id=1, date=1)
    with pytest.raises(AssertionError) as e:
        mock_cache.get_coverage(report, "")
    assert str(e.value) == "Missing report myrepo/myhash/all:all"

    # Report available online
    mock_cache.bucket.add_mock_blob("myrepo/myhash/all:all.json.zstd")

    # Coverage available
    coverage = mock_cache.get_coverage(report, "")
    assert coverage == {
        "children": [],
        "coveragePercent": 0.0,
        "path": "",
        "type": "directory",
        "changeset": "myhash",
    }

    # Remove local file
    path = os.path.join(mock_cache.reports_dir, "myrepo", "myhash", "all:all.json")
    assert os.path.exists(path)
    os.unlink(path)

    # Coverage still available
    coverage = mock_cache.get_coverage(report, "")
    assert coverage == {
        "children": [],
        "coveragePercent": 0.0,
        "path": "",
        "type": "directory",
        "changeset": "myhash",
    }

    # Make invalid json
    assert os.path.exists(path)
    with open(path, "a") as f:
        f.write("break")

    # Coverage still available
    coverage = mock_cache.get_coverage(report, "")
    assert coverage == {
        "children": [],
        "coveragePercent": 0.0,
        "path": "",
        "type": "directory",
        "changeset": "myhash",
    }
    assert os.path.exists(path)
    assert isinstance(json.load(open(path)), dict)
