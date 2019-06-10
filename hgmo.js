/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

"use strict";

let filename = "";
let revision = "";
const linePattern = new RegExp("^l([0-9]+)$");

document.querySelectorAll("title").forEach(title => {
  const titlePattern = new RegExp("^mozilla-central: ([^@]+)@([0-9a-f]+)(?: \\(annotated\\))?$");
  const m = title.innerText.match(titlePattern);
  if (m) {
    filename = m[1];
    revision = m[2];
  }
});

async function applyOverlay(revPromise, path) {
  let result = await getCoverage(revPromise, path);
  if (!result.hasOwnProperty("coverage")) {
    throw new Error("No 'coverage' field");
  }
  const data = result["coverage"];
  document.querySelectorAll("[id^='l']").forEach(e => {
    const m = e.id.match(linePattern);
    if (!m) {
      return;
    }
    const linenum = m[1];
    if (data.hasOwnProperty(linenum)) {
      e.style.backgroundColor = (data[linenum] > 0) ? "greenyellow" : "tomato";
    }
  });
}

function removeOverlay() {
  document.querySelectorAll("[id^='l']").forEach(e => {
    const m = e.id.match(linePattern);
    if (m) {
      e.style.backgroundColor = "";
    }
  });
}

const div_headers = document.querySelectorAll(".page_header");
if (div_headers.length > 1) {
  throw new Error("Only one .page_header was expected");
}
const div_header = div_headers[0];
const button = injectToggle(revision, filename);
div_header.append(button);
