/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

"use strict";

const hgurlPattern = new RegExp("^http[s]?://hg\\.mozilla\\.org/mozilla-central/annotate/([0-9a-f]+)/([^#]+)#l([0-9]+)$");
// fileinfo: filename => { revision => [{line, element}, ...] }
const fileinfo = {};
document.querySelectorAll("#frames table:first-of-type td > a[href^='https://hg.mozilla.org/mozilla-central/annotate/']").forEach(a => {
  const m = a.href.match(hgurlPattern);
  if (!m) {
    return;
  }
  const filename = m[2];
  if (!isCoverageSupported(filename)) {
    return;
  }
  const line = m[3];
  if (line === "0") { // shouldn't happen... but irl it happens
    return;
  }
  const revision = m[1].slice(0, 12); // shorten the revision
  const info = {
    "line": line,
    "element": a.parentNode
  };
  let finfo;
  if (filename in fileinfo) {
    finfo = fileinfo[filename];
  } else {
    finfo = fileinfo[filename] = {};
  }
  if (revision in finfo) {
    finfo[revision].push(info);
  } else {
    finfo[revision] = [info];
  }
});

if (Object.keys(fileinfo).length != 0) {
  const spinnerDiv = document.createElement("div");
  spinnerDiv.classList.add("gecko_coverage_loader", "gecko_coverage_loader_socorro");
  spinnerDiv.style.display = "inline-block";

  for (const [filename, info] of Object.entries(fileinfo)) {
    for (const [revision, lineElements] of Object.entries(info)) {
      // Add the spinners
      for (const le of lineElements) {
        const e = spinnerDiv.cloneNode();
        le.element.append(e);
        le.element = e;
      }
      fetchCoverage(revision, filename).then(data => {
        if (data !== null && !data.hasOwnProperty("error")) {
          for (const le of lineElements) {
            const line = le.line;
            if (line in data) {
              // line is covered or uncovered
              le.element.parentNode.style.backgroundColor = data[line] == 0 ? "tomato" : "greenyellow";
            }
          }
        }
        // Remove all the spinners
        for (const le of lineElements) {
          le.element.className = "";
        }
      });
    }
  }
}
