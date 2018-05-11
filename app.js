function assert(condition, message) {
  if (!condition) {
    throw new Error(message || "Assertion failed");
  }
}

let get_data = function() {
  let files = null;
  return async function() {
    if (!files) {
      let response = await fetch('https://raw.githubusercontent.com/marco-c/code-coverage-reports/master/zero_coverage_report.json');
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

function get_min_date(oldDate, newDate) {
  if (!oldDate) {
    return newDate;
  }
  if (Date.parse(newDate) < Date.parse(oldDate)) {
    return newDate;
  }

  return oldDate;
}

function getBaseStats(file, children) {
  return {'children': children,
          'funcs': file.funcs,
          'first_push_date': file.first_push_date,
          'last_push_date': file.last_push_date,
          'size': file.size,
          'commits': file.commits};
}

function cumStats(prevStats, newStats) {
  prevStats.children += 1;
  prevStats.funcs += newStats.funcs;
  prevStats.size += newStats.size;
  prevStats.commits += newStats.commits;
  prevStats.first_push_date = get_min_date(prevStats.first_push_date, newStats.first_push_date);
  prevStats.last_push_date = get_min_date(prevStats.last_push_date, newStats.last_push_date);
}

function getSpanForValue(value) {
  const span = document.createElement('span');
  span.innerText = value == 0 ? '' : value;
  return span;
}

function getSpanForFile(data, dir, entry) {
  const span = document.createElement('span');
  span.className = 'filename';
  const a = document.createElement('a');
  a.textContent = entry;
  const path = dir + entry;
  if (data.children != 0) {
    a.href = '#' + path;
  } else {
    a.target = '_blank';
    a.href = 'https://codecov.io/gh/mozilla/gecko-dev/src/master/' + path;
  }
  span.appendChild(a);
  return span;
}

function getFileSize(size) {
  if (size >= 1e6) {
    return (size / 1e6).toFixed(2) + 'M';
  } else if (size >= 1e3) {
    return (size / 1e3).toFixed(1) + 'K';
  }
  return size;
}

async function generate(dir='') {
  while (dir.endsWith('/')) dir = dir.substring(0, dir.length - 1);
  dir += '/';
  if (dir == '/') {
    dir = '';
  }

  const data = await get_data();
  let files = data['files'].filter(file => file.name.startsWith(dir));
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
        cumStats(map.get(rest), file);
      } else {
        map.set(rest, getBaseStats(file, 1));
      }
    } else {
      if (map.has(rest)) {
        console.warn(rest + ' is already in map.');
      }
      map.set(rest, getBaseStats(file, 0));
    }
  }

  const columns = [['File name', (x, dir, entry) => getSpanForFile(x, dir, entry)],
                   ['Children', (x) => getSpanForValue(x.children)],
                   ['Functions', (x) => getSpanForValue(x.funcs)],
                   ['First push', (x) => getSpanForValue(x.first_push_date)],
                   ['Last push', (x) => getSpanForValue(x.last_push_date)],
                   ['Size', (x) => getSpanForValue(getFileSize(x.size))],
                   ['Commits', (x) => getSpanForValue(x.commits)]];

  const output = document.createElement('div');
  output.id = 'output';

  const global = document.createElement('div');
  global.textContent = files.length + ' files';
  output.appendChild(global);
  output.appendChild(document.createElement('br'));
  output.appendChild(document.createElement('br'));

  const header = document.createElement('div');
  header.className = 'header';
  columns.forEach(([name, ]) => {
    const span = getSpanForValue(name);
    if (name === 'File name') {
      span.className = 'filename';
    }
    header.append(span);
  });
  output.append(header);

  for (const [entry, stats] of sort_entries(Array.from(map.entries()))) {
    const entryElem = document.createElement('div');
    entryElem.className = 'row';
    columns.forEach(([, func]) => {
      entryElem.append(func(stats, dir, entry));
    });
    output.appendChild(entryElem);
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
