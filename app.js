function assert(condition, message) {
  if (!condition) {
    throw new Error(message || "Assertion failed");
  }
}

let onLoad = new Promise(function(resolve, reject) {
  window.onload = resolve;
});

let get_files = function() {
  let files = null;
  return async function() {
    if (!files) {
      let response = await fetch('https://raw.githubusercontent.com/marco-c/code-coverage-reports/master/zero_coverage_files.json');
      files = await response.json();
    }

    return files;
  };
}();

let get_third_party_paths = function() {
  let paths = null;
  return async function() {
    if (!paths) {
      let response = await fetch('https://hg.mozilla.org/mozilla-central/raw-file/tip/tools/rewriting/ThirdPartyPaths.txt');
      paths = (await response.text()).split('\n').filter(path => path != '');
    }

    return paths;
  };
}();

function sort_entries(entries) {
  return entries.sort(([dir1, len1], [dir2, len2]) => {
    if (len1 != len2) {
      return len1 < len2;
    }

    return dir1 > dir2;
  });
}

function is_third_party_enabled() {
  let third_party = document.getElementById('third_party');
  return third_party.checked;
}

async function filter_third_party(files) {
  if (is_third_party_enabled()) {
    return files;
  }

  let paths = await get_third_party_paths();

  return files.filter(file => {
    for (let path of paths) {
      if (file.startsWith(path)) {
        return false;
      }
    }

    return true;
  });
}

async function doit(dir='') {
  while (dir.endsWith('/')) dir = dir.substring(0, dir.length - 1);
  dir += '/';
  if (dir == '/') {
    dir = '';
  }

  let files = (await get_files()).filter(file => file.startsWith(dir));
  files = await filter_third_party(files);

  let map = new Map();

  for (let file of files) {
    let rest = file.substring(dir.lastIndexOf('/') + 1);

    if (rest.includes('/')) {
      rest = rest.substring(0, rest.indexOf('/'));
      let num = 1;
      if (map.has(rest)) {
        num = map.get(rest) + 1;
      }
      map.set(rest, num);
    } else {
      if (map.has(rest)) {
        console.warn(rest + ' is already in map.');
      }
      map.set(rest, 0);
    }
  }

  let output = document.createElement('div');
  output.id = 'output';

  let global = document.createElement('span');
  global.textContent = files.length + ' files.';
  output.appendChild(global);
  output.appendChild(document.createElement('br'));
  output.appendChild(document.createElement('br'));

  let arr = [];
  for (let entry of map) arr.push(entry);

  for (let [entry, len] of sort_entries(arr)) {
    let entryElem = document.createElement('span');
    if (len != 0) {
      let a = document.createElement('a');
      a.textContent = entry;
      a.href = '#' + dir + entry;
      entryElem.appendChild(a);
      entryElem.appendChild(document.createTextNode(' with ' + len + ' files.'));
    } else {
      let a = document.createElement('a');
      a.target = '_blank';
      a.textContent = entry;
      a.href = 'https://codecov.io/gh/marco-c/gecko-dev/src/master/' + dir + entry;
      entryElem.appendChild(a);
    }
    output.appendChild(entryElem);
    output.appendChild(document.createElement('br'));
  }

  document.getElementById('output').replaceWith(output);
}

function go() {
  doit(window.location.hash.substring(1));
}

async function main() {
  await onLoad;

  let third_party = document.getElementById('third_party');
  third_party.onchange = go;

  window.onhashchange = go;

  go();
}

main();
