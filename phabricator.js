/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

'use strict';

let parentRevisionPromise;

function getLines(block) {
  return block.querySelectorAll('table.differential-diff tbody tr th:first-child');
}

function applyOverlay(block, data) {
  for (let line of getLines(block)) {
    let lineNumber = parseInt(line.textContent);
    if (isNaN(lineNumber)) {
      continue;
    }
    if (!data.hasOwnProperty(lineNumber)) {
      continue;
    }

    if (data[lineNumber] > 0) {
      line.style.backgroundColor = 'greenyellow';
    } else {
      line.style.backgroundColor = 'tomato';
    }
  }
}

function removeOverlay(block) {
  for (let line of getLines(block)) {
    line.style.backgroundColor = '';
  }
}

async function injectButton(block) {
  const path = block.querySelector('h1.differential-file-icon-header').textContent;
  if (!isCoverageSupported(path)) {
    return;
  }

  const buttonDiv = block.querySelector('div.differential-changeset-buttons');
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'Code Coverage';
  button.disabled = true;
  button.title = 'Loading...';
  button.className = 'button button-grey';
  button.style['cursor'] = 'not-allowed';
  buttonDiv.append(button);

  const parentRevision = await parentRevisionPromise;
  let data;
  if (!parentRevision) {
    button.title = 'Error fetching parent revision.';
    return;
  } else {
    const coverage = await fetchCoverage(parentRevision, path);
    if (!coverage.hasOwnProperty('data') || coverage.hasOwnProperty('error')) {
      button.title = 'Failed fetching coverage data.'
      return;
    } else {
      data = coverage.data;
    }
  }

  let enabled = false;
  async function toggle() {
    enabled = !enabled;

    if (enabled) {
      applyOverlay(block, data);
    } else {
      removeOverlay(block);
    }
  }

  // Enable the code coverage button.
  button.onclick = toggle;
  button.style['cursor'] = 'default';
  button.title = 'Toggle viewing code coverage.';
  button.disabled = false;
}

async function fetchParentRevision() {
  const revisionPHIDpattern = RegExp('/(PHID-DREV-[^/]*)/');
  const href = document.querySelector('a.policy-link[data-sigil=workflow]').getAttribute('href');
  const diffIdMatch = href.match(revisionPHIDpattern);
  if (!diffIdMatch) {
    console.error('diff id not found!');
    return null;
  }
  const phid = diffIdMatch[1];

  const revisionResponse = await phidToHg(phid);
  if (revisionResponse.error) {
    console.error(revisionResponse.error);
    return null;
  } else {
    return revisionResponse.revision;
  }
}

function inject() {
  parentRevisionPromise = fetchParentRevision();
  document.querySelectorAll('div[data-sigil=differential-changeset]').forEach(injectButton);
}

inject();
