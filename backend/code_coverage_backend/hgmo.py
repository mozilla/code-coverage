# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from typing import Dict
from typing import Tuple

import requests
import structlog

logger = structlog.get_logger(__name__)

__hgmo: Dict[str, Tuple[int, float]] = {}

HGMO_REVISION_URL = (
    "https://hg.mozilla.org/{repository}/json-automationrelevance/{revision}"
)
HGMO_PUSHES_URL = "https://hg.mozilla.org/{repository}/json-pushes"


def hgmo_revision_details(repository, changeset):
    """
    HGMO helper to retrieve details for a changeset
    """
    # Check cache first
    key = (repository, changeset)
    if key in __hgmo:
        return __hgmo[key]

    url = HGMO_REVISION_URL.format(repository=repository, revision=changeset)
    resp = requests.get(url)
    resp.raise_for_status()
    assert "changesets" in resp.json(), "Missing changesets"
    data = resp.json()["changesets"][-1]
    assert "pushid" in data, "Missing pushid"
    out = data["pushid"], data["date"][0]

    # Store in cache
    __hgmo[key] = out
    return out


def hgmo_pushes(repository, min_push_id, nb_pages, chunk_size=8):
    """
    HGMO helper to list all pushes in a limited number of pages
    """
    params = {"version": 2}
    if min_push_id is not None:
        assert isinstance(min_push_id, int)
        params["startID"] = min_push_id
        params["endID"] = min_push_id + chunk_size

    for page in range(nb_pages):
        r = requests.get(HGMO_PUSHES_URL.format(repository=repository), params=params)
        data = r.json()

        # Sort pushes to go from oldest to newest
        pushes = sorted(
            [(int(push_id), push) for push_id, push in data["pushes"].items()],
            key=lambda p: p[0],
        )
        if not pushes:
            return

        for push in pushes:
            yield push

        newest = pushes[-1][0]
        params["startID"] = newest
        params["endID"] = newest + chunk_size
