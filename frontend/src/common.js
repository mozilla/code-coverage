import Mustache from 'mustache';

export const REV_LATEST = 'latest';

function assert(condition, message) {
  if (!condition) {
    throw new Error(message || "Assertion failed");
  }
}

function domContentLoaded() {
  return new Promise(resolve => document.addEventListener('DOMContentLoaded', resolve));
}
export const DOM_READY = domContentLoaded();

export async function main(load, display, opts) {
  // Immediately listen to DOM event

  // Load initial data before DOM is available
  let data = await load();

  // Wait for DOM to be ready before displaying
  await DOM_READY;
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


// Coverage retrieval.

const COVERAGE_BACKEND_HOST = 'https://coverage.moz.tools';

function cache_get(cache, key) {
  if (key in cache) {
    return cache[key].val;
  }
}

function cache_set(cache, key, value) {
  let now = new Date().getTime() / 1000;

  // If the cache got too big, remove all elements that were added more
  // than 15 minutes ago.
  if (Object.keys(cache).length > 100) {
    for (let key in cache) {
      if (cache[key].time < now - 15 * 60) {
        delete cache[key];
      }
    }
  }

  cache[key] = {
    'val': value,
    'time': now,
  };
}

let path_coverage_cache = {};
export async function get_path_coverage(path, changeset) {
  let data = cache_get(path_coverage_cache, `${changeset}_${path}`);
  if (data) {
    return data;
  }

  let params = `path=${path}`;
  if (changeset && changeset !== REV_LATEST) {
    params += `&changeset=${changeset}`;
  }
  let response = await fetch(`${COVERAGE_BACKEND_HOST}/v2/path?${params}`).catch(alert);
  if (response.status !== 200) {
    throw new Error(response.status + ' - ' + response.statusText);
  }
  data = await response.json();

  cache_set(path_coverage_cache, `${changeset}_${path}`, data);

  return data;
}

let history_cache = {};
export async function get_history(path) {
  // Backend needs path without trailing /
  if (path && path.endsWith('/')) {
    path = path.substring(0, path.length-1);
  }

  let data = cache_get(history_cache, path);
  if (data) {
    return data;
  }

  let response = await fetch(`${COVERAGE_BACKEND_HOST}/v2/history?path=${path}`);
  data = await response.json();

  cache_set(history_cache, path, data);

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

let zero_coverage_cache = {};
export async function get_zero_coverage_data() {
  let data = cache_get(zero_coverage_cache, '');
  if (data) {
    return data;
  }

  let response = await fetch('https://index.taskcluster.net/v1/task/project.releng.services.project.production.code_coverage_bot.latest/artifacts/public/zero_coverage_report.json');
  data = await response.json();

  cache_set(zero_coverage_cache, '', data);

  return data;
}


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

export async function get_source(file) {
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

export async function filter_third_party(files) {
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

export function filter_languages(files) {
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

export function filter_headers(files) {
  if (is_enabled('headers')) {
    return files;
  }

  return files.filter(file => !file.path.endsWith('.h'));
}

export function filter_completely_uncovered(files) {
  if (!is_enabled('completely_uncovered')) {
    return files;
  }

  return files.filter(file => file.uncovered);
}

export function filter_last_push_date(files) {
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

// Build the urls for a breadcrumb Navbar from a path
export function build_navbar(path, revision) {
  if (path.endsWith('/')) {
    path = path.substring(0, path.length-1);
  }
  let base = '';
  let links = [
    {
      'name': 'mozilla-central',
      'path': '',
    }
  ];
  return links.concat(path.split('/').map(file => {
    base += (base ? '/' : '') + file;
    return {
      'name': file,
      'path': base,
    };
  }));
}

// Display helpers
function canDisplay() {
  return document.readyState == 'complete';
}

export function message(cssClass, message) {
  if(!canDisplay()) return;

  let box = document.getElementById('message');
  box.className = 'message ' + cssClass;
  box.textContent = message;
  box.style.display = 'block';
}

export function hide(id) {
  if(!canDisplay()) return;

  let box = document.getElementById(id);
  box.style.display = 'none';
}

export function show(id, node) {
  if(!canDisplay()) return;

  let box = document.getElementById(id);
  box.style.display = 'block';
  if (node) {
    box.replaceWith(node);
  }
  return box;
}

export function render(template, data, target) {
  var output = Mustache.render(document.getElementById(template).innerHTML, data);
  let box = document.getElementById(target);
  box.innerHTML = output;
  box.style.display = 'block';
  return box;
}
