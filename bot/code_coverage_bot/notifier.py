# -*- coding: utf-8 -*-
import structlog

from code_coverage_bot.phabricator import parse_revision_id
from code_coverage_bot.phabricator import parse_revision_url
from code_coverage_bot.secrets import secrets
from code_coverage_bot.taskcluster import taskcluster_config

logger = structlog.get_logger(__name__)


def notify_email(revision, changesets, changesets_coverage):
    """
    Send an email to admins when low coverage for new commits is detected
    """
    notify_service = taskcluster_config.get_service("notify")

    content = ""
    for changeset in changesets:
        desc = changeset["desc"].split("\n")[0]

        # Lookup changeset coverage from phabricator uploader
        rev_id = parse_revision_id(changeset["desc"])
        if rev_id is None:
            continue
        coverage = changesets_coverage.get(changeset["node"])
        if coverage is None:
            logger.warn("No coverage found", changeset=changeset)
            continue

        # Calc totals for all files
        covered = sum(
            c["lines_covered"] + c["lines_unknown"] for c in coverage["paths"].values()
        )
        added = sum(c["lines_added"] for c in coverage["paths"].values())

        if covered < 0.4 * added:
            url = parse_revision_url(changeset["desc"])
            content += f"* [{desc}]({url}): {covered} covered out of {added} added.\n"

    if content == "":
        return
    elif len(content) > 102400:
        # Content is 102400 chars max
        content = content[:102000] + "\n\n... Content max limit reached!"

    for email in secrets[secrets.EMAIL_ADDRESSES]:
        notify_service.email(
            {
                "address": email,
                "subject": "Coverage patches for {}".format(revision),
                "content": content,
                "template": "fullscreen",
            }
        )

    return content
