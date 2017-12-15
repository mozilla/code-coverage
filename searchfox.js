(function() {
  const breadcrumbs = document.querySelector('.breadcrumbs');
  if (breadcrumbs) {
    // Get the currently open file path.
    const path = breadcrumbs.lastElementChild.href.split('/mozilla-central/source/')[1];

    // Get the current revision.
    const revPattern = new RegExp('/mozilla-central/commit/([0-9a-f]+)"');
    const revSpan = document.getElementById('rev-id');
    const m = revSpan.innerHTML.match(revPattern);
    const rev = m[1];

    // Don't do anything if this isn't a file.
    const panel = document.querySelector('#panel-content');
    if (!panel) {
      return;
    }

    // TODO: Hook it up to actually do something
    const enabled_div = document.createElement('div');
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.setAttribute('checked', 'checked');
    checkbox.id = "code_coverage_enabled";
    const label = document.createElement('label');
    label.setAttribute("for", "code_coverage_enabled");
    label.textContent = 'Code Coverage Overlay';
    enabled_div.appendChild(checkbox);
    enabled_div.appendChild(label);
    breadcrumbs.parentNode.insertBefore(enabled_div, breadcrumbs);
    // TODO: Also make pressing 'C' toggle code coverage overlay.

    setTimeout(function() {

    // TODO: Map git to hg rev first
    fetch(`https://api.pub.build.mozilla.org/mapper/gecko-dev/rev/git/${request.gitrev}`)
    .then(response => response.text())
    .then(result => result.split(' ')[1]);
    browser.runtime.sendMessage({
      type: 'file',
      gitrev: rev,
      path: path,
    })
    .then(result => {
      console.log(result);
      // TODO: Actually retrieve coverage data.
      for (let [l, c] of Object.entries(result['coverage'])) {
          const line_no = document.getElementById('l' + i);
          const line = document.getElementById('line-' + i);
          if (c > 0) {
            line_no.style.backgroundColor = 'greenyellow';
            line.style.backgroundColor = 'greenyellow';
          } else {
            line_no.style.backgroundColor = 'tomato';
            line.style.backgroundColor = 'tomato';
          }
      }
    });

    }, 0);
  }
})();
