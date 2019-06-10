/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

'use strict';

async function fetchCoverage(rev, path) {
  let response = await fetch(`${CONFIG.BACKEND_URL}/v2/path?path=${path}&changeset=${rev}`);
  return await response.json();
}

function wait(time) {
  return new Promise(resolve => setTimeout(resolve, time));
}

async function waitIdle(time) {
  await wait(time);
  return new Promise(resolve => requestIdleCallback(resolve));
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
