import { REV_LATEST } from "./common.js";
import { display } from "./index.js";

export function readRoute() {
  // Reads all filters from current URL hash
  const hash = window.location.hash.substring(1);
  const pairs = hash.split("&");
  const out = {};
  pairs.forEach((pair) => {
    const [key, value] = pair.split("=");
    if (!key) {
      return;
    }
    out[decodeURIComponent(key)] = decodeURIComponent(value);
  });

  // Default values
  if (!out.revision) {
    out.revision = REV_LATEST;
  }
  if (!out.path) {
    out.path = "";
  }

  return out;
}

export function buildRoute(params) {
  // Add all params on top of current route
  let route = readRoute();
  if (params) {
    route = { ...route, ...params };
  }

  // Build query string from filters
  return (
    "#" +
    Object.keys(route)
      .map((k) => encodeURIComponent(k) + "=" + encodeURIComponent(route[k]))
      .join("&")
  );
}

export function updateRoute(params) {
  // Update full hash with an updated url
  // Will trigger full load + display update
  window.location.hash = buildRoute(params);
}

export async function updateRouteImmediate(hash, data) {
  // Will trigger only a display update, no remote data will be fetched

  // Update route without reloading content
  history.pushState(null, null, hash);

  // Update the route stored in data
  data.route = readRoute();
  await display(data);
}

export function monitorOptions(currentData) {
  // Monitor input & select changes
  const fields = document.querySelectorAll("input, select, a.scroll");
  for (const field of fields) {
    if (field.classList.contains("scroll")) {
      // On a scroll event, update display without any data loading
      field.onclick = async (evt) => {
        evt.preventDefault();
        updateRouteImmediate(evt.target.hash, currentData);
      };
    } else if (field.type === "text") {
      // React on enter
      field.onkeydown = async (evt) => {
        if (evt.keyCode === 13) {
          const params = {};
          params[evt.target.name] = evt.target.value;
          updateRoute(params);
        }
      };
    } else {
      // React on change
      field.onchange = async (evt) => {
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
