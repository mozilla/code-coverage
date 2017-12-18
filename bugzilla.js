/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

"use strict";

function wait(time) {
  return new Promise(resolve => setTimeout(resolve, time));
}

async function retrieveData(rev) {
  let ready = false;
  do {
    let response = await fetch(`https://uplift.shipit.staging.mozilla-releng.net/coverage/changeset_summary/${rev}`);

    if (response.status == 202) {
      await wait(5000);
      continue;
    }

    let result = await response.json();
    result['rev'] = rev;
    return result;
  } while (!ready);
}

(function() {
const container = document.getElementById("module-details-content");
if (container) {
  const hgurlPattern = new RegExp("^http[s]?://hg\\.mozilla\\.org/mozilla-central/rev/([0-9a-f]+)$");
  const revs = [];
  let isFirst = false;
  let currentCommentId = "";
  document.querySelectorAll(".comment-text > a").forEach(a => {
    const parentId = a.parentNode.attributes.id;
    if (parentId !== currentCommentId) {
        // we're in a new comment
        currentCommentId = parentId;
        isFirst = false;
    }
    const prev = a.previousSibling;
    if (prev == null || (prev.previousSibling == null && !prev.textContent.trim())) {
        // the first element in the comment is the likn (no text before)
        isFirst = true;
    }
    if (isFirst) {
        // so we take the first link and the following ones only if they match the pattern
        const link = a.href;
        const m = link.match(hgurlPattern);
        if (m != null) {
          let rev = m[1];
          if (rev.length > 12) {
            rev = rev.slice(0, 12);
          }
          revs.push(rev);
        }
    }
  });

  if (revs.length == 0) {
    return;
  }

  let styleEl = document.createElement('style');
  document.head.appendChild(styleEl);
  styleEl.sheet.insertRule(`@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}`, 0);
  styleEl.sheet.insertRule(`.loader {
  border: 3px solid #f3f3f3;
  border-radius: 50%;
  border-top: 3px solid green;
  width: 13px;
  height: 13px;
  animation: spin 2s linear infinite;
}`, 1);

  const mainDiv = document.createElement('div');
  mainDiv.className = 'field';
  const nameDiv = document.createElement('div');
  nameDiv.className = 'name';
  nameDiv.textContent = 'Code Coverage:';
  mainDiv.appendChild(nameDiv);
  const valueDiv = document.createElement('div');
  valueDiv.classList.add('loader');
  mainDiv.appendChild(valueDiv);
  container.appendChild(mainDiv);

  let promises = revs.map(retrieveData);

  Promise.all(promises)
  .then(results => {
    let added = 0;
    let covered = 0;
    for (let result of results) {
      added += result.commit_added;
      covered += result.commit_covered;
    }

    valueDiv.classList.remove('loader');
    const span = document.createElement('span');
    if (added > 0) {
      span.style.color = 'green';
      span.textContent = `${covered} lines covered out of ${added} lines added`;
    } else {
      span.textContent = 'No instrumented lines added.'
    }
    valueDiv.appendChild(span);
    valueDiv.appendChild(document.createTextNode(' ('));
    let aElems = results.filter(result => result.commit_added > 0).map(result => {
      let a = document.createElement('a');
      a.href = `https://firefox-code-coverage.herokuapp.com/#/changeset/${result.rev}`;
      a.textContent = result.rev;
      return a;
    });

    for (let i = 0; i < aElems.length; i++) {
      valueDiv.appendChild(aElems[i]);
      if (i != aElems.length - 1) {
        valueDiv.appendChild(document.createTextNode(', '));
      }
    }

    valueDiv.appendChild(document.createTextNode(')'));
  });
}
})();
