# -*- coding: utf-8 -*-

import os
import re
from typing import Any
from typing import Dict
from typing import Iterator
from typing import List
from typing import Optional
from typing import Tuple

import hglib
import structlog
from libmozdata.phabricator import BuildState
from libmozdata.phabricator import PhabricatorAPI
from libmozdata.phabricator import PhabricatorRevisionNotFoundException

from code_coverage_bot.secrets import secrets
from tools.code_coverage_tools import COVERAGE_EXTENSIONS

logger = structlog.get_logger(__name__)

PHABRICATOR_REVISION_REGEX = re.compile(
    "Differential Revision: (https://phabricator.services.mozilla.com/D([0-9]+))"
)


def parse_revision_id(desc):
    match = PHABRICATOR_REVISION_REGEX.search(desc)
    if not match:
        return None
    return int(match.group(2))


def parse_revision_url(desc):
    match = PHABRICATOR_REVISION_REGEX.search(desc)
    if not match:
        return None
    return match.group(1)


class PhabricatorUploader(object):
    def __init__(
        self, repo_dir: str, revision: str, warnings_enabled: Optional[bool] = True
    ) -> None:
        self.repo_dir = repo_dir
        self.revision = revision
        self.warnings_enabled = warnings_enabled

        # Read third party exclusion lists from repo
        third_parties = os.path.join(
            self.repo_dir, "tools/rewriting/ThirdPartyPaths.txt"
        )
        if os.path.exists(third_parties):
            self.third_parties = [line.rstrip() for line in open(third_parties)]
        else:
            self.third_parties = []
            logger.warn("Missing third party exclusion list", path=third_parties)

    def run_annotate(
        self, hg: hglib.client, rev: str, path: str
    ) -> Optional[Tuple[Tuple[str, int], ...]]:
        args = hglib.util.cmdbuilder(
            b"annotate",
            os.path.join(self.repo_dir, path).encode("ascii"),
            r=rev,
            line=True,
            changeset=True,
        )
        try:
            out = hg.rawcommand(args)
        except hglib.error.CommandError as e:
            if b"no such file in rev" not in e.err:
                raise

            # The file was removed.
            return None

        def _collect() -> Iterator[Tuple[str, int]]:
            for line in out.splitlines():
                orig_changeset, orig_line, _ = line.split(b":", 2)
                yield orig_changeset.decode("ascii"), int(orig_line)

        return tuple(_collect())

    def _find_coverage(self, report: dict, path: str) -> Optional[List[int]]:
        """
        Find coverage value in a covdir report
        """
        parts = path.split("/")
        for part in filter(None, parts):
            if part not in report["children"]:
                # Only send warning for non 3rd party + supported extensions
                if self.is_third_party(path):
                    logger.info("Path not found in report for third party", path=path)
                elif not self.is_supported_extension(path):
                    logger.info(
                        "Path not found in report for unsupported extension", path=path
                    )
                else:
                    if self.warnings_enabled:
                        logger.warn("Path not found in report", path=path)
                    else:
                        logger.info("Path not found in report", path=path)
                return None
            report = report["children"][part]

        return report["coverage"]

    def _build_coverage_map(self, annotate, coverage_record):
        # We can't use plain line numbers to map coverage data from the build changeset to the
        # changeset of interest, indeed there could be intermediate changesets between them
        # modifying the same lines, thus displacing the line numbers.
        # In order to uniquely identify lines, and thus map coverage data, we use the annotate
        # data. The line number and changeset where a line was introduced are unique, so whenever
        # they match in the annotate data of the two changesets, we can be sure that it is the
        # same line.
        coverage_map = {}

        for lineno, (orig_changeset, orig_line) in enumerate(annotate):
            key = (orig_changeset, orig_line)
            # Assume lines outside the coverage record are uncoverable (that happens for the
            # last few lines of a file, they are not considered by instrumentation).
            coverage_map[key] = (
                coverage_record[lineno] if lineno < len(coverage_record) else -1
            )

        return coverage_map

    def _apply_coverage_map(self, annotate, coverage_map):
        phab_coverage_data = ""

        for orig_changeset, orig_line in annotate:
            key = (orig_changeset, orig_line)
            if key in coverage_map:
                count = coverage_map[key]
                if count == -1:
                    # A non-executable line.
                    phab_coverage_data += "N"
                elif count > 0:
                    phab_coverage_data += "C"
                else:
                    phab_coverage_data += "U"
            else:
                # We couldn't find the original changeset-original line in the annotate data for the build changeset,
                # this means that this line has been overwritten by another changeset.
                phab_coverage_data += "X"

        return phab_coverage_data

    def is_third_party(self, path):
        """
        Check a file against known list of third party paths
        """
        for third_party in self.third_parties:
            if path.startswith(third_party):
                return True
        return False

    def is_supported_extension(self, path):
        """
        Check a file has a supported extension
        """
        _, ext = os.path.splitext(path)
        if not ext:
            return False
        return ext[1:] in COVERAGE_EXTENSIONS

    def generate(
        self, hg: hglib.client, report: dict, changesets: List[dict]
    ) -> Dict[str, Dict[str, Any]]:
        results = {}

        # Skip merge changesets and backouts.
        changesets = [
            changeset
            for changeset in changesets
            if not any(
                text in changeset["desc"].split("\n")[0]
                for text in ["r=merge", "a=merge"]
            )
            and len(changeset["backsoutnodes"]) == 0
        ]

        all_paths = tuple(
            set(sum((changeset["files"] for changeset in changesets), []))
        )

        coverage_records_by_path = {
            path: self._find_coverage(report, path) for path in all_paths
        }

        # Retrieve the annotate data for the build changeset.

        build_annotate_by_path = {
            path: self.run_annotate(hg, self.revision, path)
            for path in all_paths
            if coverage_records_by_path.get(path) is not None
        }

        for changeset in changesets:
            # Retrieve the revision ID for this changeset.
            revision_id = parse_revision_id(changeset["desc"])

            results[changeset["node"]] = {
                "revision_id": revision_id,
                "paths": {},
            }

            # For each file...
            for path in changeset["files"]:
                # Retrieve the coverage data.
                coverage_record = coverage_records_by_path.get(path)
                if coverage_record is None:
                    continue

                # Retrieve the annotate data for the build changeset.
                build_annotate = build_annotate_by_path.get(path)
                if build_annotate is None:
                    # This means the file has been removed by another changeset, but if this is the
                    # case, then we shouldn't have a coverage record and so we should have *continue*d
                    # earlier.
                    assert (
                        False
                    ), "Failure to retrieve annotate data for the build changeset"

                # Build the coverage map from the annotate data and the coverage data of the build changeset.
                coverage_map = self._build_coverage_map(build_annotate, coverage_record)

                # Retrieve the annotate data for the changeset of interest.
                annotate = self.run_annotate(hg, changeset["node"], path)
                if annotate is None:
                    # This means the file has been removed by this changeset, and maybe was brought back by a following changeset.
                    continue

                # List lines added by this patch
                lines_added = [
                    lineno
                    for lineno, (annotate_changeset, _) in enumerate(annotate)
                    if annotate_changeset == changeset["node"][:12]
                ]

                # Apply the coverage map on the annotate data of the changeset of interest.
                coverage = self._apply_coverage_map(annotate, coverage_map)

                results[changeset["node"]]["paths"][path] = {
                    "lines_added": sum(
                        coverage[line] != "N"
                        for line in lines_added
                        if line < len(coverage)
                    ),
                    "lines_unknown": sum(
                        coverage[line] == "X"
                        for line in lines_added
                        if line < len(coverage)
                    ),
                    "lines_covered": sum(
                        coverage[line] == "C"
                        for line in lines_added
                        if line < len(coverage)
                    ),
                    "coverage": coverage,
                }

        return results

    def upload(self, report: dict, changesets: List[dict]) -> Dict[str, Dict[str, Any]]:
        with hglib.open(self.repo_dir) as hg:
            results = self.generate(hg, report, changesets)

        if secrets[secrets.PHABRICATOR_ENABLED]:
            phabricator = PhabricatorAPI(
                secrets[secrets.PHABRICATOR_TOKEN], secrets[secrets.PHABRICATOR_URL]
            )
        else:
            phabricator = None

        for result in results.values():
            rev_id = result["revision_id"]
            if rev_id is None:
                continue

            # Only upload raw coverage data to Phabricator, not stats
            coverage = {path: cov["coverage"] for path, cov in result["paths"].items()}
            logger.info("{} coverage: {}".format(rev_id, coverage))

            if not phabricator or not coverage:
                continue

            try:
                rev_data = phabricator.load_revision(rev_id=rev_id)
                phabricator.upload_coverage_results(
                    rev_data["fields"]["diffPHID"], coverage
                )
                # XXX: This is only necessary until https://bugzilla.mozilla.org/show_bug.cgi?id=1487843 is resolved.
                phabricator.upload_lint_results(
                    rev_data["fields"]["diffPHID"], BuildState.Pass, []
                )
            except PhabricatorRevisionNotFoundException:
                logger.warn("Phabricator revision not found", rev_id=rev_id)

        return results
