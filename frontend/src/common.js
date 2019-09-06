import Mustache from 'mustache';
import { buildRoute, readRoute, updateRoute } from './route.js';
import {ZERO_COVERAGE_FILTERS} from './zero_coverage_report.js';

export const REV_LATEST = 'latest';

function domContentLoaded() {
  return new Promise(resolve => document.addEventListener('DOMContentLoaded', resolve));
}
export const DOM_READY = domContentLoaded();

export async function main(load, display) {
  // Load initial data before DOM is available
  let data = await load();

  // Wait for DOM to be ready before displaying
  await DOM_READY;
  await display(data);
  monitor_options();

  // Full workflow, loading then displaying data
  // used for following updates
  let full = async function() {
    let data = await load();
    await display(data);
    monitor_options();
  };

  // React to url changes
  window.onhashchange = full;
}

// Coverage retrieval.

const COVERAGE_BACKEND_HOST = process.env.BACKEND_URL;

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
export async function get_path_coverage(path, changeset, platform, suite) {
  let cache_key = `${changeset}_${path}_${platform}_${suite}`;
  let data = cache_get(path_coverage_cache, cache_key);
  if (data) {
    return data;
  }

  let params = `path=${path}`;
  if (changeset && changeset !== REV_LATEST) {
    params += `&changeset=${changeset}`;
  }
  if (platform && platform !== 'all') {
    params += `&platform=${platform}`;
  }
  if (suite && suite !== 'all') {
    params += `&suite=${suite}`;
  }
  let response = await fetch(`${COVERAGE_BACKEND_HOST}/v2/path?${params}`).catch(alert);
  if (response.status !== 200) {
    throw new Error(response.status + ' - ' + response.statusText);
  }
  data = await response.json();

  cache_set(path_coverage_cache, cache_key, data);

  return data;
}

let history_cache = {};
export async function get_history(path, platform, suite) {
  // Backend needs path without trailing /
  if (path && path.endsWith('/')) {
    path = path.substring(0, path.length-1);
  }

  let cache_key = `${path}_${platform}_${suite}`;
  let data = cache_get(history_cache, cache_key);
  if (data) {
    return data;
  }

  let params = `path=${path}`;
  if (platform && platform !== 'all') {
    params += `&platform=${platform}`;
  }
  if (suite && suite !== 'all') {
    params += `&suite=${suite}`;
  }
  let response = await fetch(`${COVERAGE_BACKEND_HOST}/v2/history?${params}`);
  data = await response.json();

  cache_set(history_cache, cache_key, data);

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


let filters_cache = {};
export async function get_filters() {
  let data = cache_get(filters_cache, '');
  if (data) {
    return data;
  }

  let response = await fetch(`${COVERAGE_BACKEND_HOST}/v2/filters`);
  data = await response.json();

  cache_set(filters_cache, '', data);

  return data;
}


// Option handling.

export function is_enabled(opt) {
  let route = readRoute();
  let value = 'off';
  if (route[opt]) {
    value = route[opt];
  } else if (ZERO_COVERAGE_FILTERS[opt]) {
    value = ZERO_COVERAGE_FILTERS[opt].default_value;
  }
  return value === 'on';
}

function monitor_options() {
  // Monitor input & select changes
  let fields = document.querySelectorAll('input, select');
  for(let field of fields) {
    if (field.type == 'text') {
      // React on enter
      field.onkeydown = async (evt) => {
        if(evt.keyCode === 13) {
          let params = {};
          params[evt.target.name] = evt.target.value;
          updateRoute(params);
        }
      }
    } else {
      // React on change
      field.onchange = async (evt) => {
        let value = evt.target.value;
        if (evt.target.type == 'checkbox') {
          value = evt.target.checked ? 'on' : 'off';
        }
        let params = {};
        params[evt.target.name] = value;
        updateRoute(params);
      }
    }
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
      'route': buildRoute({path: '', revision})
    }
  ];
  return links.concat(path.split('/').map(file => {
    base += (base ? '/' : '') + file;
    return {
      'name': file,
      'route': buildRoute({path: base, revision})
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
