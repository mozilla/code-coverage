const REV_LATEST = 'latest';

function assert(condition, message) {
  if (!condition) {
    throw new Error(message || "Assertion failed");
  }
}

function domContentLoaded() {
  return new Promise(resolve => document.addEventListener('DOMContentLoaded', resolve));
}

async function main(load, display, opts) {
  // Immediately listen to DOM event
  let domReady = domContentLoaded();

  // Load initial data before DOM is available
  let data = await load();

  // Wait for DOM to be ready before displaying
  await domReady;
  await display(data);

  // Full workflow, loading then displaying data
  // used for following updates
  let full = async function() {
    let data = await load();
    await display(data);
  };
  monitor_options(opts, full);
  window.onhashchange = full;
}


// Visualization.

function getSpanForValue(value) {
  const span = document.createElement('span');
  span.innerText = value == 0 ? '' : value;
  return span;
}


// Coverage retrieval.

const COVERAGE_BACKEND_HOST = 'https://coverage.moz.tools';

async function get_path_coverage(path, changeset) {
  let params = `path=${path}`;
  if (changeset && changeset !== REV_LATEST) {
    params += `&changeset=${changeset}`;
  }
  let response = await fetch(`${COVERAGE_BACKEND_HOST}/v2/path?${params}`).catch(alert);
  if (response.status !== 200) {
    throw new Error(response.status + ' - ' + response.statusText);
  }
  return await response.json();
}

async function get_latest() {
  let response = await fetch(`${COVERAGE_BACKEND_HOST}/v2/latest`);
  return (await response.json())[0]['revision'];
}

async function get_file_coverage(changeset, path) {
  let response = await fetch(`${COVERAGE_BACKEND_HOST}/v2/path?changeset=${changeset}&path=${path}`);
  return await response.json();
}

async function get_history(path) {
  // Backend needs path without trailing /
  if (path && path.endsWith('/')) {
    path = path.substring(0, path.length-1);
  }

  let response = await fetch(`${COVERAGE_BACKEND_HOST}/v2/history?path=${path}`);
  let data = await response.json();

  // Check data has coverage values
  // These values are missing when going above 2 levels right now
  let coverage = data.filter(point => {
    return point.coverage !== null;
  });
  if (coverage.length === 0 ) {
    console.warn(`No history data for ${path}`);
    return null;
  }

  return data;
}

let get_zero_coverage_data = function() {
  let files = null;
  return async function() {
    if (!files) {
      let response = await fetch('https://index.taskcluster.net/v1/task/project.releng.services.project.production.code_coverage_bot.latest/artifacts/public/zero_coverage_report.json');
      files = await response.json();
    }

    return files;
  };
}();


// Option handling.

function is_enabled(opt) {
  let elem = document.getElementById(opt);
  return elem.checked;
}

function monitor_options(opts, callback) {
  for (let opt of opts) {
    let elem = document.getElementById(opt);
    elem.onchange = callback;
  }
}


// hgmo.

async function get_source(file) {
  let response = await fetch(`https://hg.mozilla.org/mozilla-central/raw-file/tip/${file}`);
  return await response.text();
}


// Filtering.

let get_third_party_paths = function() {
  let paths = null;
  return async function() {
    if (!paths) {
      let response = await get_source('tools/rewriting/ThirdPartyPaths.txt');
      paths = response.split('\n').filter(path => path != '');
    }

    return paths;
  };
}();

async function filter_third_party(files) {
  if (is_enabled('third_party')) {
    return files;
  }

  let paths = await get_third_party_paths();

  return files.filter(file => {
    for (let path of paths) {
      if (file.path.startsWith(path)) {
        return false;
      }
    }

    return true;
  });
}

function filter_languages(files) {
  let cpp = is_enabled('cpp');
  let cpp_extensions = ['c', 'cpp', 'cxx', 'cc', 'h', 'hh', 'hxx', 'hpp', 'inl', 'inc'];
  let js = is_enabled('js');
  let js_extensions = ['js', 'jsm', 'xml', 'xul', 'xhtml', 'html'];
  let java = is_enabled('java');
  let java_extensions = ['java'];
  let rust = is_enabled('rust');
  let rust_extensions = ['rs'];

  return files.filter(file => {
    if (file.type == "directory") {
      return true;
    } else if (cpp_extensions.find(ext => file.path.endsWith('.' + ext))) {
      return cpp;
    } else if (js_extensions.find(ext => file.path.endsWith('.' + ext))) {
      return js;
    } else if (rust_extensions.find(ext => file.path.endsWith('.' + ext))) {
      return rust;
    } else if (java_extensions.find(ext => file.path.endsWith('.' + ext))) {
      return java;
    } else {
      console.warn('Unknown language for ' + file.path);
      return false;
    }
  });
}

function filter_headers(files) {
  if (is_enabled('headers')) {
    return files;
  }

  return files.filter(file => !file.path.endsWith('.h'));
}

function filter_completely_uncovered(files) {
  if (!is_enabled('completely_uncovered')) {
    return files;
  }

  return files.filter(file => file.uncovered);
}

function filter_last_push_date(files) {
  let elem = document.getElementById('last_push');
  let upper_limit = new Date();
  let lower_limit = new Date();

  if (elem.value == 'one_year') {
    lower_limit.setFullYear(upper_limit.getFullYear() - 1);
  } else if (elem.value == 'two_years') {
    upper_limit.setFullYear(upper_limit.getFullYear() - 1);
    lower_limit.setFullYear(lower_limit.getFullYear() - 2);
  } else if (elem.value == 'older_than_two_years') {
    upper_limit.setFullYear(upper_limit.getFullYear() - 2);
    lower_limit = new Date('1970-01-01T00:00:00Z');
  } else {
    return files;
  }

  return files.filter(file => {
    let last_push_date = new Date(file.last_push_date);
    if (last_push_date.getTime() <= upper_limit.getTime()
      && last_push_date.getTime() >= lower_limit.getTime()) {
      return true;
    } else {
      return false;
    }
  });
}

// Build a breadcrumb Navbar from a path
function navbar(path, revision) {
  let files = path.split('/');
  files.unshift(null); // add mozilla-central
  let nav = document.createElement('nav');
  let base = '';
  let href = revision !== undefined ? (revision + ':') : '';
  files.forEach(file => {
    let a = document.createElement('a');
    if (file !== null) {
      base += (base ? '/' : '') + file;
      a.href = '#' + href + base;
      a.textContent = file;
    }else{
      a.href = '#' + href;
      a.textContent = 'mozilla-central';
    }
    nav.appendChild(a);
  });
  return nav;
}


// Display helpers
function canDisplay() {
  return document.readyState == 'complete';
}

function message(cssClass, message) {
  if(!canDisplay()) return;

  let box = document.getElementById('message');
  box.className = 'message ' + cssClass;
  box.textContent = message;
  box.style.display = 'block';
}

function hide(id) {
  if(!canDisplay()) return;

  let box = document.getElementById(id);
  box.style.display = 'none';
}

function show(id, node) {
  if(!canDisplay()) return;

  let box = document.getElementById(id);
  box.style.display = 'block';
  if (node) {
    box.replaceWith(node);
  }
  return box;
}
