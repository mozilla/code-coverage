import {
  hide,
  message,
  buildNavbar,
  isEnabled,
  render,
  filterThirdParty,
  filterLanguages,
  filterHeaders,
  filterCompletelyUncovered,
  filterLastPushDate
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

export function zeroCoverageMenu(route) {
  const context = {
    filters: Object.entries(ZERO_COVERAGE_FILTERS).map(([key, filter]) => {
      return {
        key,
        message: filter.name,
        checked: isEnabled(key)
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

function sortEntries(entries) {
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

function getMinDate(oldDate, newDate) {
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
    lastPushDate: file.lastPushDate,
    size: file.size,
    commits: file.commits
  };
}

function cumStats(prevStats, newStats) {
  prevStats.children += 1;
  prevStats.funcs += newStats.funcs;
  prevStats.size += newStats.size;
  prevStats.commits += newStats.commits;
  prevStats.first_push_date = getMinDate(
    prevStats.first_push_date,
    newStats.first_push_date
  );
  prevStats.lastPushDate = getMinDate(
    prevStats.lastPushDate,
    newStats.lastPushDate
  );
}

export async function zeroCoverageDisplay(data, dir) {
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
  files = await filterThirdParty(files);
  files = filterLanguages(files);
  files = filterHeaders(files);
  files = filterCompletelyUncovered(files);
  files = filterLastPushDate(files);

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
    entries: sortEntries(Array.from(map.entries())),
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
    navbar: buildNavbar(dir),
    total: files.length
  };

  hide("message");
  render("zerocoverage", context, "output");
}
