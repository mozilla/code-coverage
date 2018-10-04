/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

'use strict';

async function fetchCoverage(rev, path) {
  let response = await fetch(`https://coverage.moz.tools/coverage/file?changeset=${rev}&path=${path}`);
  return await response.json();
}

function wait(time) {
  return new Promise(resolve => setTimeout(resolve, time));
}

async function waitIdle(time) {
  await wait(time);
  return new Promise(resolve => requestIdleCallback(resolve));
}

async function fetchChangesetCoverage(rev) {
  let ready = false;
  do {
    let response = await fetch(`https://coverage.moz.tools/coverage/changeset_summary/${rev}`);

    if (response.status == 202) {
      await wait(5000);
      continue;
    }

    let result = await response.json();
    result['rev'] = rev;
    return result;
  } while (!ready);
}

async function phidToHg(phid) {
  let response = await fetch(`https://coverage.moz.tools/phabricator/base_revision_from_phid/${phid}`);
  return await response.json();
}

async function gitToHg(gitrev) {
  let response = await fetch(`https://mapper.mozilla-releng.net/gecko-dev/rev/git/${gitrev}`);
  if (!response.ok) {
    throw new Error(`Error retrieving git to mercurial mapping for ${gitrev}.`);
  }
  let text = await response.text();
  return text.split(' ')[1];
}

function isCoverageSupported(path) {
  return SUPPORTED_EXTENSIONS.findIndex(ext => path.endsWith(`.${ext}`)) != -1;
}
