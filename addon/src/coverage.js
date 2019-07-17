/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

'use strict';

import {BACKEND_URL} from './config';
const extensions = require('extensions.json')

export async function fetchCoverage(rev, path) {
  let response = await fetch(`${BACKEND_URL}/v2/path?path=${path}&changeset=${rev}`);
  return await response.json();
}

export async function gitToHg(gitrev) {
  let response = await fetch(`https://mapper.mozilla-releng.net/gecko-dev/rev/git/${gitrev}`);
  if (!response.ok) {
    throw new Error(`Error retrieving git to mercurial mapping for ${gitrev}.`);
  }
  let text = await response.text();
  return text.split(' ')[1];
}

export function isCoverageSupported(path) {
  return extensions.findIndex(ext => path.endsWith(`.${ext}`)) != -1;
}
