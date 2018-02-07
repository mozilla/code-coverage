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

let get_functions_stats = function() {
  let files = null;
  return async function() {
    if (!files) {
      let response = await fetch('https://raw.githubusercontent.com/marco-c/code-coverage-reports/master/zero_coverage_functions.json');
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
  return entries.sort(([dir1, stats1], [dir2, stats2]) => {
    if (stats1.children != stats2.children) {
      return stats1.children < stats2.children;
    }

    if (stats1.funcs != stats2.funcs) {
      return stats1.funcs < stats2.funcs;
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
      if (file.name.startsWith(path)) {
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

  return files.filter(file => !file.name.endsWith('.h'));
}

function filter_languages(files) {
  let cpp = is_enabled('cpp');
  let cpp_extensions = ['c', 'cpp', 'cxx', 'cc', 'h', 'hh', 'hxx', 'hpp', 'inl', 'inc'];
  let js = is_enabled('js');
  let js_extensions = ['js', 'jsm', 'xml', 'xul', 'xhtml', 'html'];

  return files.filter(file => {
      if (cpp_extensions.find(ext => file.name.endsWith('.' + ext))) {
        return cpp;
      } else if (js_extensions.find(ext => file.name.endsWith('.' + ext))) {
        return js;
      } else {
        console.warn('Unknown language for ' + file.name);
        return false;
      }
  });
}

function filter_completely_uncovered(files) {
  if (!is_enabled('completely_uncovered')) {
    return files;
  }

  return files.filter(file => file.uncovered);
}

async function generate(dir='') {
  while (dir.endsWith('/')) dir = dir.substring(0, dir.length - 1);
  dir += '/';
  if (dir == '/') {
    dir = '';
  }

  let uncovered_files = (await get_files()).filter(file => file.startsWith(dir));
  let files = (await get_functions_stats()).filter(file => file.name.startsWith(dir));
  let uncovered_files_set = new Set();
  for (let file of uncovered_files) {
      uncovered_files_set.add(file);
  }
  for (let obj of files) {
      obj.uncovered = uncovered_files_set.has(obj.name);
  }
  files = await filter_third_party(files);
  files = filter_languages(files);
  files = filter_headers(files);
  files = filter_completely_uncovered(files);

  let map = new Map();

  for (let file of files) {
    let rest = file.name.substring(dir.lastIndexOf('/') + 1);

    if (rest.includes('/')) {
      rest = rest.substring(0, rest.indexOf('/'));
      if (map.has(rest)) {
        existing_num = map.get(rest);
        existing_num.children += 1;
        existing_num.funcs += file.funcs;
      } else {
        map.set(rest, {'children': 1, 'funcs': file.funcs});
      }
    } else {
      if (map.has(rest)) {
        console.warn(rest + ' is already in map.');
      }
      map.set(rest, {'children': 0, 'funcs': file.funcs});
    }
  }

  let output = document.createElement('div');
  output.id = 'output';

  let global = document.createElement('span');
  global.textContent = files.length + ' files.';
  output.appendChild(global);
  output.appendChild(document.createElement('br'));
  output.appendChild(document.createElement('br'));

  for (let [entry, stats] of sort_entries(Array.from(map.entries()))) {
    let entryElem = document.createElement('span');
    let a = document.createElement('a');
    a.textContent = entry;
    entryElem.appendChild(a);
    if (stats.children != 0) {
      a.href = '#' + dir + entry;
      entryElem.appendChild(document.createTextNode(` - ${stats.children} files and ${stats.funcs} functions`));
    } else {
      a.target = '_blank';
      a.href = 'https://codecov.io/gh/marco-c/gecko-dev/src/master/' + dir + entry;
      entryElem.appendChild(document.createTextNode(` - ${stats.funcs} functions`));
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

  let opts = ['third_party', 'headers', 'completely_uncovered', 'cpp', 'js'];
  for (let opt of opts) {
    let elem = document.getElementById(opt);
    elem.onchange = go;
  }

  window.onhashchange = go;

  go();
}

main();
