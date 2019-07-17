/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

'use strict';

import {getCoverage} from './button';

let lineNoMap = (function() {
  let mapper;

  return function(l) {
    if (!mapper) {
      if (document.getElementById('l1')) {
        mapper = l => `l${l}`;
      } else if (document.getElementById('1')) {
        mapper = l => l;
      } else {
        throw new Error('Unknown line number element.');
      }
    }

    return mapper(l);
  };
})();

export async function applyOverlay(revPromise, path) {
  let result = await getCoverage(revPromise, path);

  if (!result.hasOwnProperty('coverage')) {
    throw new Error('No \'coverage\' field');
  }
  for (var l in result.coverage) {
    l = parseInt(l) + 1;
    const line_no = document.getElementById(lineNoMap(l));
    const line = document.getElementById(`line-${l}`);
    if (result.coverage[l] > 0) {
      line_no.style.backgroundColor = 'greenyellow';
      line.style.backgroundColor = 'greenyellow';
    } else {
      line_no.style.backgroundColor = 'tomato';
      line.style.backgroundColor = 'tomato';
    }
  }
}

export function removeOverlay() {
  let l = 1;
  var line_no = true;
  while (line_no) {
    line_no = document.getElementById(lineNoMap(l));
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
export function getPath() {
  const breadcrumbs = document.querySelector('.breadcrumbs');
  if (!breadcrumbs) {
    return;
  }

  return breadcrumbs.lastElementChild.href.split('/mozilla-central/source/')[1];
}

export function getNavigationPanel() {
  return document.getElementById('panel-content');
}
