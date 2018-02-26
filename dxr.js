/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

'use strict';

(function() {
  // Don't do anything if this isn't a file.
  const panel = getNavigationPanel();
  if (!panel) {
    return;
  }

  const path = getPath();
  if (!path || !isCoverageSupported(path)) {
    return;
  }

  // Get the current revision.
  const revPattern = new RegExp('Mercurial \\(([0-9a-f]+)\\)');
  const m = panel.innerHTML.match(revPattern);
  const revPromise = Promise.resolve(m[1]);

  const button = injectToggle(revPromise, path);
  if (!button) {
    return;
  }

  let treeSelector = document.getElementById('tree-selector');
  treeSelector.appendChild(button);
})();
