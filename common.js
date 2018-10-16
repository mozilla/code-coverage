function assert(condition, message) {
  if (!condition) {
    throw new Error(message || "Assertion failed");
  }
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


