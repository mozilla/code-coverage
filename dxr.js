/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

"use strict";

let result;

async function applyOverlay(rev, path) {
  if (!result) {
    let response = await fetch(`https://uplift.shipit.staging.mozilla-releng.net/coverage/file?changeset=${rev}&path=${path}`);
    result = await response.json();
  }

  for (let [l, c] of Object.entries(result)) {
    const line_no = document.getElementById(l);
    const line = document.getElementById('line-' + l);
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
    const line_no = document.getElementById(l);
    if (!line_no) {
      break;
    }
    const line = document.getElementById(`line-${l}`);

    line_no.style.backgroundColor = '';
    line.style.backgroundColor = '';

    l += 1;
  }
}

(function() {
  const breadcrumbs = document.querySelector('.breadcrumbs');
  if (!breadcrumbs) {
    return;
  }

  // Don't do anything if this isn't a file.
  const panel = document.querySelector('#panel-content');
  if (!panel) {
    return;
  }

  // Get the currently open file path.
  const path = breadcrumbs.lastElementChild.href.split('/mozilla-central/source/')[1];

  // Get the current revision.
  const revPattern = new RegExp('Mercurial \\(([0-9a-f]+)\\)');
  const navigation = document.getElementById('panel-content');
  if (!navigation) {
    return;
  }
  const m = navigation.innerHTML.match(revPattern);
  const rev = m[1];

  let button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'Code Coverage';
  button.style.backgroundColor = 'white';
  button.style.marginBottom = '.2rem';
  button.style.padding = '.3rem';
  button.style.border = '1px solid #999';
  button.style.width = 'auto';
  button.style.minWidth = '100px';
  button.style.borderRadius = '.2rem';
  button.style.cursor = 'pointer';

  let enabled = false;
  function toggle() {
    enabled = !enabled;
    if (enabled) {
      applyOverlay(rev, path);
      button.style.backgroundColor = 'lightgrey';
    } else {
      removeOverlay();
      button.style.backgroundColor = 'white';
    }
  }

  button.onclick = toggle;
  let treeSelector = document.getElementById('tree-selector');
  treeSelector.appendChild(button);

  document.onkeyup = function(e) {
    if (e.key == 'c') {
      toggle();
    }
  };
})();
