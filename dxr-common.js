/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

'use strict';

let resultPromise;

let lineNoMap;
if (document.getElementById('l1')) {
  lineNoMap = l => `l${l}`;
} else if (document.getElementById('1')) {
  lineNoMap = l => l;
}

async function getCoverage(revPromise, path) {
  if (!resultPromise) {
    resultPromise = (async function() {
      const rev = await revPromise;
      return fetchCoverage(rev, path);
    })();
  }

  return resultPromise;
}

async function applyOverlay(revPromise, path) {
  let result = await getCoverage(revPromise, path);

  for (let [l, c] of Object.entries(result)) {
    const line_no = document.getElementById(lineNoMap(l));
    const line = document.getElementById(`line-${l}`);
    if (c > 0) {
      line_no.style.backgroundColor = 'greenyellow';
      line.style.backgroundColor = 'greenyellow';
    } else {
      line_no.style.backgroundColor = 'tomato';
      line.style.backgroundColor = 'tomato';
    }
  }
}

function removeOverlay() {
  let l = 1;
  while (true) {
    const line_no = document.getElementById(lineNoMap(l));
    if (!line_no) {
      break;
    }
    const line = document.getElementById(`line-${l}`);

    line_no.style.backgroundColor = '';
    line.style.backgroundColor = '';

    l += 1;
  }
}

// Get the currently open file path.
function getPath() {
  const breadcrumbs = document.querySelector('.breadcrumbs');
  if (!breadcrumbs) {
    return;
  }

  return breadcrumbs.lastElementChild.href.split('/mozilla-central/source/')[1];
}

function getNavigationPanel() {
  return document.getElementById('panel-content');
}

function injectToggle(revPromise, path) {
  // Preload coverage data.
  getCoverage(revPromise, path);

  const spinner = document.createElement('div');
  spinner.classList.add('gecko_coverage_loader', 'gecko_coverage_loader_dxr');

  let button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'Code Coverage ';
  button.className = 'gecko_code_coverage_toggle_button';

  let enabled = false;
  async function toggle() {
    enabled = !enabled;
    if (enabled) {
      button.appendChild(spinner);
      await applyOverlay(revPromise, path, lineNoMap);
      button.removeChild(spinner);
      button.style.backgroundColor = 'lightgrey';
    } else {
      removeOverlay(lineNoMap);
      button.style.backgroundColor = 'white';
    }
  }

  button.onclick = toggle;

  document.onkeyup = function(e) {
    if (e.key == 'c') {
      toggle();
    }
  };

  return button;
}
