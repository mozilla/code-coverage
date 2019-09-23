import Mustache from "mustache";
import { buildRoute, readRoute, updateRoute } from "./route.js";
import { ZERO_COVERAGE_FILTERS } from "./zero_coverage_report.js";

export const REV_LATEST = "latest";

function domContentLoaded() {
  return new Promise(resolve =>
    document.addEventListener("DOMContentLoaded", resolve)
  );
}
export const DOM_READY = domContentLoaded();

export async function main(load, display) {
  // Load initial data before DOM is available
  const data = await load();

  // Wait for DOM to be ready before displaying
  await DOM_READY;
  await display(data);
  monitorOptions();

  // Full workflow, loading then displaying data
  // used for following updates
  const full = async function() {
    const data = await load();
    await display(data);
    monitorOptions();
  };

  // React to url changes
  window.onhashchange = full;
}

// Coverage retrieval.

const COVERAGE_BACKEND_HOST = process.env.BACKEND_URL;

function cacheGet(cache, key) {
  if (key in cache) {
    return cache[key].val;
  }
  return null;
}

function cacheSet(cache, key, value) {
  const now = new Date().getTime() / 1000;

  // If the cache got too big, remove all elements that were added more
  // than 15 minutes ago.
  if (Object.keys(cache).length > 100) {
    for (const key in cache) {
      if (cache[key].time < now - 15 * 60) {
        delete cache[key];
      }
    }
  }

  cache[key] = {
    val: value,
    time: now
  };
}

const pathCoverageCache = {};
export async function getPathCoverage(path, changeset, platform, suite) {
  const cacheKey = `${changeset}_${path}_${platform}_${suite}`;
  let data = cacheGet(pathCoverageCache, cacheKey);
  if (data) {
    return data;
  }

  let params = `path=${path}`;
  if (changeset && changeset !== REV_LATEST) {
    params += `&changeset=${changeset}`;
  }
  if (platform && platform !== "all") {
    params += `&platform=${platform}`;
  }
  if (suite && suite !== "all") {
    params += `&suite=${suite}`;
  }
  const response = await fetch(
    `${COVERAGE_BACKEND_HOST}/v2/path?${params}`
  ).catch(alert);
  if (response.status !== 200) {
    throw new Error(response.status + " - " + response.statusText);
  }
  data = await response.json();

  cacheSet(pathCoverageCache, cacheKey, data);

  return data;
}

const historyCache = {};
export async function getHistory(path, platform, suite) {
  // Backend needs path without trailing /
  if (path && path.endsWith("/")) {
    path = path.substring(0, path.length - 1);
  }

  const cacheKey = `${path}_${platform}_${suite}`;
  let data = cacheGet(historyCache, cacheKey);
  if (data) {
    return data;
  }

  let params = `path=${path}`;
  if (platform && platform !== "all") {
    params += `&platform=${platform}`;
  }
  if (suite && suite !== "all") {
    params += `&suite=${suite}`;
  }
  const response = await fetch(`${COVERAGE_BACKEND_HOST}/v2/history?${params}`);
  data = await response.json();

  cacheSet(historyCache, cacheKey, data);

  // Check data has coverage values
  // These values are missing when going above 2 levels right now
  const coverage = data.filter(point => {
    return point.coverage !== null;
  });
  if (coverage.length === 0) {
    console.warn(`No history data for ${path}`);
    return null;
  }

  return data;
}

const zeroCoverageCache = {};
export async function getZeroCoverageData() {
  let data = cacheGet(zeroCoverageCache, "");
  if (data) {
    return data;
  }

  const response = await fetch(
    "https://index.taskcluster.net/v1/task/project.releng.services.project.production.code_coverage_bot.latest/artifacts/public/zero_coverage_report.json"
  );
  data = await response.json();

  cacheSet(zeroCoverageCache, "", data);

  return data;
}

const filtersCache = {};
export async function getFilters() {
  let data = cacheGet(filtersCache, "");
  if (data) {
    return data;
  }

  const response = await fetch(`${COVERAGE_BACKEND_HOST}/v2/filters`);
  data = await response.json();

  cacheSet(filtersCache, "", data);

  return data;
}

// Option handling.

export function isEnabled(opt) {
  const route = readRoute();
  let value = "off";
  if (route[opt]) {
    value = route[opt];
  } else if (ZERO_COVERAGE_FILTERS[opt]) {
    value = ZERO_COVERAGE_FILTERS[opt].default_value;
  }
  return value === "on";
}

function monitorOptions() {
  // Monitor input & select changes
  const fields = document.querySelectorAll("input, select");
  for (const field of fields) {
    if (field.type === "text") {
      // React on enter
      field.onkeydown = async evt => {
        if (evt.keyCode === 13) {
          const params = {};
          params[evt.target.name] = evt.target.value;
          updateRoute(params);
        }
      };
    } else {
      // React on change
      field.onchange = async evt => {
        let value = evt.target.value;
        if (evt.target.type === "checkbox") {
          value = evt.target.checked ? "on" : "off";
        }
        const params = {};
        params[evt.target.name] = value;
        updateRoute(params);
      };
    }
  }
}

// hgmo.

export async function getSource(file) {
  const response = await fetch(
    `https://hg.mozilla.org/mozilla-central/raw-file/tip/${file}`
  );
  return response.text();
}

// Filtering.

const getThirdPartyPaths = (function() {
  let paths = null;
  return async function() {
    if (!paths) {
      const response = await getSource("tools/rewriting/ThirdPartyPaths.txt");
      paths = response.split("\n").filter(path => path !== "");
    }

    return paths;
  };
})();

export async function filterThirdParty(files) {
  if (isEnabled("third_party")) {
    return files;
  }

  const paths = await getThirdPartyPaths();

  return files.filter(file => {
    for (const path of paths) {
      if (file.path.startsWith(path)) {
        return false;
      }
    }

    return true;
  });
}

export function filterLanguages(files) {
  const cpp = isEnabled("cpp");
  const cppExtensions = [
    "c",
    "cpp",
    "cxx",
    "cc",
    "h",
    "hh",
    "hxx",
    "hpp",
    "inl",
    "inc"
  ];
  const js = isEnabled("js");
  const jsExtensions = ["js", "jsm", "xml", "xul", "xhtml", "html"];
  const java = isEnabled("java");
  const javaExtensions = ["java"];
  const rust = isEnabled("rust");
  const rustExtensions = ["rs"];

  return files.filter(file => {
    if (file.type === "directory") {
      return true;
    } else if (cppExtensions.find(ext => file.path.endsWith("." + ext))) {
      return cpp;
    } else if (jsExtensions.find(ext => file.path.endsWith("." + ext))) {
      return js;
    } else if (rustExtensions.find(ext => file.path.endsWith("." + ext))) {
      return rust;
    } else if (javaExtensions.find(ext => file.path.endsWith("." + ext))) {
      return java;
    }
    console.warn("Unknown language for " + file.path);
    return false;
  });
}

export function filterHeaders(files) {
  if (isEnabled("headers")) {
    return files;
  }

  return files.filter(file => !file.path.endsWith(".h"));
}

export function filterCompletelyUncovered(files) {
  if (!isEnabled("completely_uncovered")) {
    return files;
  }

  return files.filter(file => file.uncovered);
}

export function filterLastPushDate(files) {
  const elem = document.getElementById("last_push");
  const upperLimit = new Date();
  let lowerLimit = new Date();

  if (elem.value === "one_year") {
    lowerLimit.setFullYear(upperLimit.getFullYear() - 1);
  } else if (elem.value === "two_years") {
    upperLimit.setFullYear(upperLimit.getFullYear() - 1);
    lowerLimit.setFullYear(lowerLimit.getFullYear() - 2);
  } else if (elem.value === "older_than_two_years") {
    upperLimit.setFullYear(upperLimit.getFullYear() - 2);
    lowerLimit = new Date("1970-01-01T00:00:00Z");
  } else {
    return files;
  }

  return files.filter(file => {
    const lastPushDate = new Date(file.lastPushDate);
    if (
      lastPushDate.getTime() <= upperLimit.getTime() &&
      lastPushDate.getTime() >= lowerLimit.getTime()
    ) {
      return true;
    }
    return false;
  });
}

// Build the urls for a breadcrumb Navbar from a path
export function buildNavbar(path, revision) {
  if (path.endsWith("/")) {
    path = path.substring(0, path.length - 1);
  }
  let base = "";
  const links = [
    {
      name: "mozilla-central",
      route: buildRoute({ path: "", revision })
    }
  ];
  return links.concat(
    path.split("/").map(file => {
      base += (base ? "/" : "") + file;
      return {
        name: file,
        route: buildRoute({ path: base, revision })
      };
    })
  );
}

// Display helpers
function canDisplay() {
  return document.readyState === "complete";
}

export function message(cssClass, message) {
  if (!canDisplay()) {
    return;
  }

  const box = document.getElementById("message");
  box.className = "message " + cssClass;
  box.textContent = message;
  box.style.display = "inherit";
}

export function hide(id) {
  if (!canDisplay()) {
    return;
  }

  const box = document.getElementById(id);
  box.style.display = "none";
}

export function show(id, node) {
  if (!canDisplay()) {
    return null;
  }

  const box = document.getElementById(id);
  box.style.display = "inherit";
  if (node) {
    box.replaceWith(node);
  }
  return box;
}

export function render(template, data, target) {
  const output = Mustache.render(
    document.getElementById(template).innerHTML,
    data
  );
  const box = document.getElementById(target);

  // The innerHTML check is disabled because we trust Mustache output
  // eslint-disable-next-line no-unsanitized/property
  box.innerHTML = output;

  box.style.display = "inherit";
  return box;
}
