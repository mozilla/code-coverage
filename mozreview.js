/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

'use strict';

let allRevsPromise;

async function waitExists(elemFinder) {
  while (true) {
    let elem = elemFinder();
    if (elem) {
      return elem;
    }

    await waitIdle(50);
  }
}

async function waitHidden(elem) {
  while (true) {
    let hidden = (elem.style.display === 'none');
    if (hidden) {
      return;
    }

    await waitIdle(50);
  }
}

let resultPromises = {};
async function getChangesetData(path) {
  if (!resultPromises[path]) {
    resultPromises[path] = (async function() {
      const allRevs = await allRevsPromise;

      const curRev = allRevs[0]['node'];
      const publicRev = allRevs[allRevs.length - 1]['node'];

      const middleRevs = allRevs.slice(1, allRevs.length - 1);

      try {
        const coveragePromise = fetchCoverage(publicRev, path);
        const annotatePromise = fetchAnnotate(curRev, path);

        const coverage = await coveragePromise;
        const annotate = await annotatePromise;

	if (!coverage.hasOwnProperty('data')) {
	  return 'error'
	}
	const coverage_data = coverage['data'];

        let result = {};

        for (const data of annotate['annotate']) {
          // Skip lines that were modified by a patch in the queue between a mozilla-central patch and the current
          // shown patch.
          if (middleRevs.includes(data['node'])) {
            continue;
          }

          const line = data['lineno'];

          if (!coverage_data.hasOwnProperty(line)) {
            continue;
          }

          result[line] = coverage_data[line];
        }

        return result;
      } catch (ex) {
        return 'error';
      }
    })();
  }

  return resultPromises[path];
}

async function applyOverlay(diff, path) {
  let result = await getChangesetData(path);
  if (result === 'error') {
    throw new Error('Error retrieving code coverage');
  }

  let lines = diff.querySelectorAll('td.l');

  for (let line of lines) {
    let line_no_elem = line.parentNode.querySelector('th');
    let line_no = parseInt(line_no_elem.textContent);
    if (isNaN(line_no)) {
      continue;
    }
    if (result.hasOwnProperty(line_no)) {
      if (result[line_no] > 0) {
        line_no_elem.style.backgroundColor = 'greenyellow';
      } else {
        line_no_elem.style.backgroundColor = 'tomato';
      }
    }
  }
}

function removeOverlay(diff) {
  let lines = diff.querySelectorAll('td.l');

  for (let line of lines) {
    let line_no_elem = line.parentNode.querySelector('th');
    line_no_elem.style.backgroundColor = '';
  }
}

async function addButton(diff, rightPos, isLatestRev) {
  const fileName = diff.querySelector('.filename-row').innerText;
  if (fileName.startsWith('commit-message')) {
    return;
  }

  if (!isCoverageSupported(fileName)) {
    return;
  }

  // Preload coverage data.
  getChangesetData(fileName);

  const coverageButton = document.createElement('button');

  function disableButton(text) {
    coverageButton.setAttribute('disabled', 'disabled');
    coverageButton.style['cursor'] = 'not-allowed';
    coverageButton.title += '- ' + text;
  }

  coverageButton.className = 'diff-file-btn';
  coverageButton.title = coverageButton.textContent = 'Code Coverage ';
  coverageButton.style['right'] = rightPos + 'px';
  if (!isLatestRev) {
    disableButton('Only available on the latest revision');
  }
  diff.appendChild(coverageButton);

  const spinner = document.createElement('div');
  spinner.classList.add('gecko_coverage_loader', 'gecko_coverage_loader_dxr');

  let enabled = false;

  async function maybeApply() {
    if (enabled) {
      coverageButton.appendChild(spinner);
      try {
        await applyOverlay(diff, fileName);
        coverageButton.classList.add('reviewed');
      } catch (ex) {
        disableButton('Error retrieving coverage information for this file');
      }
      coverageButton.removeChild(spinner);
    } else {
      removeOverlay(diff);
      coverageButton.classList.remove('reviewed');
    }
  }

  async function toggle() {
    enabled = !enabled;
    maybeApply();
  }

  coverageButton.onclick = toggle;

  /* XXX: Inject this in the page in order to detect when loading happens.
 let oldSetActivityIndicator = RB.setActivityIndicator;
  RB.setActivityIndicator = function(enabled, options) {
    oldSetActivityIndicator(enabled, options);
    maybeApply();
  };*/

  let activityIndicator = document.getElementById('activity-indicator');

  function setExpandHandlers() {
    const elems = diff.querySelectorAll('.diff-expand-btn');
    for (let elem of elems) {
      elem.onclick = async function() {
        await wait(0);

        await waitHidden(activityIndicator);

        maybeApply();
        setExpandHandlers();
      };
    }
  }

  setExpandHandlers();

  return coverageButton;
}

let buttons = [];
async function injectButtons() {
  while (buttons.length) {
    buttons.pop().remove();
  }

  let coverageButtonRightPos;
  const isLatestRev = isLatestRevision();
  const diffs = document.getElementById('diffs');
  for (const diff of diffs.children) {
    if (diff.className != 'diff-container') {
      continue;
    }

    if (typeof coverageButtonRightPos === 'undefined') {
      const reviewButton = await waitExists(() => diff.querySelector('.diff-file-btn'));
      const reviewButtonStyle = window.getComputedStyle(reviewButton);
      const reviewButtonPaddingLeft = parseInt(reviewButtonStyle['padding-left'], 10);
      const reviewButtonRight = parseInt(reviewButtonStyle['right'], 10);
      const reviewButtonWidth = reviewButton.offsetWidth;
      coverageButtonRightPos = reviewButtonRight + reviewButtonWidth + reviewButtonPaddingLeft;
    }

    let button = await addButton(diff, coverageButtonRightPos, isLatestRev);
    if (button) {
      buttons.push(button);
    }
  }
}

async function getParents(rev) {
  const hgurlPattern = new RegExp('https://reviewboard-hg.mozilla.org/gecko/rev/([0-9a-f]+)$');

  let revisions = [];

  let isPublic = false;

  do {
    let response = await fetch(`https://reviewboard-hg.mozilla.org/gecko/json-rev/${rev}`);
    let data = await response.json();

    isPublic = data['phase'] == 'public';

    revisions.push(data);

    rev = data['parents'][0];
  } while (!isPublic);

  return revisions;
}

function getRevisionLabel() {
  return document.querySelector('#diff_revision_label h1');
}

function isLatestRevision() {
  return getRevisionLabel().textContent.includes('Latest');
}

// XXX: Use https://developer.mozilla.org/en-US/Add-ons/WebExtensions/API/webNavigation/onHistoryStateUpdated to detect URL changes instead, it seems less brittle.
function checkRevisionChange(cb) {
  let observer = new MutationObserver(cb);
  observer.observe(getRevisionLabel().parentNode, { childList: true });
}

(async function() {
  const hgurlPattern = new RegExp('https://reviewboard-hg.mozilla.org/gecko/rev/([0-9a-f]+)$');
  let mozreviewRevision = '';
  const reviewRequestInputs = document.getElementById('review-request-inputs');
  for (const reviewRequestInput of reviewRequestInputs.children) {
    const m = reviewRequestInput.value.match(hgurlPattern);
    if (m != null) {
      mozreviewRevision = m[1];
      break;
    }
  }

  allRevsPromise = getParents(mozreviewRevision);

  if (document.readyState === 'complete') {
    injectButtons();
  } else {
    document.onreadystatechange = function () {
      if (document.readyState !== 'complete') {
        return;
      }

      injectButtons();
    };
  }

  checkRevisionChange(injectButtons);
})();
