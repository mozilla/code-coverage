import {REV_LATEST} from './common.js';

export function readRoute() {
  // Reads all filters from current URL hash
  let hash = window.location.hash.substring(1);
  let pairs = hash.split('&');
  let out = {}
  pairs.forEach(pair => {
    let [key, value] = pair.split('=');
    if(!key) {
      return
    }
    out[decodeURIComponent(key)] = decodeURIComponent(value);
  });

  // Default values
  if (!out.revision) {
    out.revision = REV_LATEST;
  }
  if (!out.path) {
    out.path = '';
  }

  return out;
}

export function buildRoute(params) {
  // Add all params on top of current route
  let route = readRoute();
  if (params) {
    route = {...route, ...params}
  }

  // Build query string from filters
  return '#' + Object.keys(route)
    .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(route[k]))
    .join('&');
}

export function updateRoute(params) {
  // Update full hash with an updated url
  window.location.hash = buildRoute(params);
}
