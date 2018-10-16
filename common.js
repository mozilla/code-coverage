function assert(condition, message) {
  if (!condition) {
    throw new Error(message || "Assertion failed");
  }
}


// Visualization.

function getSpanForValue(value) {
  const span = document.createElement('span');
  span.innerText = value == 0 ? '' : value;
  return span;
}


// Coverage retrieval.

const COVERAGE_BACKEND_HOST = 'https://coverage.testing.moz.tools';

async function get_path_coverage(path) {
  let response = await fetch(`${COVERAGE_BACKEND_HOST}/v2/path?path=${path}`);
  return await response.json();
}

async function get_latest() {
  let response = await fetch(`${COVERAGE_BACKEND_HOST}/coverage/latest`);
  return (await response.json())['latest_rev'];
}

async function get_file_coverage(changeset, path) {
  let response = await fetch(`${COVERAGE_BACKEND_HOST}/coverage/file?changeset=${changeset}&path=${path}`);
  return await response.json();
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
      let response = await getSource('tools/rewriting/ThirdPartyPaths.txt');
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

  return files.filter(file => {
    if (file.path.endsWith('/')) {
      return true;
    } else if (cpp_extensions.find(ext => file.path.endsWith('.' + ext))) {
      return cpp;
    } else if (js_extensions.find(ext => file.path.endsWith('.' + ext))) {
      return js;
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

  return files.filter(file => !file.name.endsWith('.h'));
}

function filter_completely_uncovered(files) {
  if (!is_enabled('completely_uncovered')) {
    return files;
  }

  return files.filter(file => file.uncovered);
}
