import {
  hide,
  message,
  build_navbar,
  render,
  filter_third_party,
  filter_languages,
  filter_headers,
  filter_completely_uncovered,
  filter_last_push_date
} from "./common.js";
import { buildRoute } from "./route.js";

export const ZERO_COVERAGE_FILTERS = {
  third_party: {
    name: "Show third-party files",
    default_value: "on"
  },
  headers: {
    name: "Show headers",
    default_value: "off"
  },
  completely_uncovered: {
    name: "Show completely uncovered files only",
    default_value: "off"
  },
  cpp: {
    name: "C/C++",
    default_value: "on"
  },
  js: {
    name: "JavaScript",
    default_value: "on"
  },
  java: {
    name: "Java",
    default_value: "on"
  },
  rust: {
    name: "Rust",
    default_value: "on"
  }
};
const ZERO_COVERAGE_PUSHES = {
  all: "All",
  one_year: "0 < 1 year",
  two_years: "1 < 2 years",
  older_than_two_years: "Older than 2 years"
};

export function zero_coverage_menu(route) {
  const context = {
    filters: Object.entries(ZERO_COVERAGE_FILTERS).map(([key, filter]) => {
      return {
        key,
        message: filter.name,
        checked: route[key] === "on"
      };
    }),
    last_pushes: Object.entries(ZERO_COVERAGE_PUSHES).map(
      ([value, message]) => {
        return {
          value,
          message,
          selected: route.last_push === value
        };
      }
    )
  };
  render("menu_zero", context, "menu");
}

function sort_entries(entries) {
  return entries
    .sort(([dir1, stats1], [dir2, stats2]) => {
      if (stats1.children !== stats2.children) {
        return stats1.children < stats2.children;
      }

      if (stats1.funcs !== stats2.funcs) {
        return stats1.funcs < stats2.funcs;
      }

      return dir1 > dir2;
    })
    .map(([dir, stats]) => {
      return { stats, dir };
    });
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
  return {
    children,
    funcs: file.funcs,
    first_push_date: file.first_push_date,
    last_push_date: file.last_push_date,
    size: file.size,
    commits: file.commits
  };
}

function cumStats(prevStats, newStats) {
  prevStats.children += 1;
  prevStats.funcs += newStats.funcs;
  prevStats.size += newStats.size;
  prevStats.commits += newStats.commits;
  prevStats.first_push_date = get_min_date(
    prevStats.first_push_date,
    newStats.first_push_date
  );
  prevStats.last_push_date = get_min_date(
    prevStats.last_push_date,
    newStats.last_push_date
  );
}

function getFileSize(size) {
  if (size >= 1e6) {
    return (size / 1e6).toFixed(2) + "M";
  } else if (size >= 1e3) {
    return (size / 1e3).toFixed(1) + "K";
  }
  return size;
}

export async function zero_coverage_display(data, dir) {
  hide("output");
  hide("history");
  message(
    "loading",
    "Loading zero coverage report for " + (dir || "mozilla-central")
  );

  while (dir.endsWith("/")) {
    dir = dir.substring(0, dir.length - 1);
  }
  dir += "/";
  if (dir === "/") {
    dir = "";
  }

  let files = data.files.filter(file => file.name.startsWith(dir));
  // TODO: Do this in the backend directly!
  files.forEach(file => {
    file.path = file.name;
  });
  files = await filter_third_party(files);
  files = filter_languages(files);
  files = filter_headers(files);
  files = filter_completely_uncovered(files);
  files = filter_last_push_date(files);

  const map = new Map();

  for (const file of files) {
    let rest = file.path.substring(dir.lastIndexOf("/") + 1);

    if (rest.includes("/")) {
      rest = rest.substring(0, rest.indexOf("/"));
      if (map.has(rest)) {
        cumStats(map.get(rest), file);
      } else {
        map.set(rest, getBaseStats(file, 1));
      }
    } else {
      if (map.has(rest)) {
        console.warn(rest + " is already in map.");
      }
      map.set(rest, getBaseStats(file, 0));
    }
  }

  const revision = data.hg_revision;
  const context = {
    current_dir: dir,
    entries: sort_entries(Array.from(map.entries())),
    entry_url() {
      const path = dir + this.dir;
      if (this.stats.children !== 0) {
        return buildRoute({
          view: "zero",
          path
        });
      }
      // Fully reset the url when moving back to browser view
      return `#view=browser&revision=${revision}&path=${path}`;
    },
    navbar: build_navbar(dir),
    total: files.length
  };

  hide("message");
  render("zerocoverage", context, "output");
}
