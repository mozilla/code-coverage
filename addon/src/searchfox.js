/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

'use strict';

import {injectToggle} from './button';
import {gitToHg, isCoverageSupported} from './coverage';
import {applyOverlay, removeOverlay, getPath, getNavigationPanel} from './dxr-common';

(async function() {
  // Don't do anything if this isn't a file.
  if (!getNavigationPanel()) {
    return;
  }

  const path = getPath();
  if (!path || !isCoverageSupported(path)) {
    return;
  }

  // Get the current revision.
  const revPattern = new RegExp('/mozilla-central/commit/([0-9a-f]+)"');
  const revSpan = document.getElementById('rev-id');
  const m = revSpan.innerHTML.match(revPattern);
  const gitRev = m[1];
  const revPromise = gitToHg(gitRev);

  const button = injectToggle(revPromise, path, applyOverlay, removeOverlay);
  if (!button) {
    return;
  }

  const breadcrumbs = document.querySelector('.breadcrumbs');
  if (!breadcrumbs) {
    return;
  }
  breadcrumbs.parentNode.insertBefore(button, breadcrumbs);
})();
