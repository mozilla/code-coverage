function assert(condition, message) {
  if (!condition) {
    throw new Error(message || "Assertion failed");
  }
}

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

function is_enabled(opt) {
  let elem = document.getElementById(opt);
  return elem.checked;
}

async function filter_third_party(files) {
  if (is_enabled('third_party')) {
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

function filter_headers(files) {
  if (is_enabled('headers')) {
    return files;
  }

  return files.filter(file => !file.endsWith('.h'));
}

function filter_languages(files) {
  let cpp = is_enabled('cpp');
  let cpp_extensions = ['c', 'cpp', 'cxx', 'cc', 'h', 'hh', 'hxx', 'hpp', 'inl', 'inc'];
  let js = is_enabled('js');
  let js_extensions = ['js', 'jsm', 'xml', 'xul', 'xhtml', 'html'];

  return files.filter(file => {
      if (cpp_extensions.find(ext => file.endsWith('.' + ext))) {
        return cpp;
      } else if (js_extensions.find(ext => file.endsWith('.' + ext))) {
        return js;
      } else {
        console.warn('Unknown language for ' + file);
        return false;
      }
  });
}

async function generate(dir='') {
  while (dir.endsWith('/')) dir = dir.substring(0, dir.length - 1);
  dir += '/';
  if (dir == '/') {
    dir = '';
  }

  let files = (await get_files()).filter(file => file.startsWith(dir));
  files = await filter_third_party(files);
  files = filter_languages(files);
  files = filter_headers(files);

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

async function main() {
  await new Promise(resolve => window.onload = resolve);

  function go() {
    generate(window.location.hash.substring(1));
  }

  let opts = ['third_party', 'headers', 'cpp', 'js'];
  for (let opt of opts) {
    let elem = document.getElementById(opt);
    elem.onchange = go;
  }

  window.onhashchange = go;

  go();
}

main();
