import {
  REV_LATEST,
  DOM_READY,
  main,
  show,
  hide,
  message,
  getPathCoverage,
  getHistory,
  getZeroCoverageData,
  buildNavbar,
  render,
  getSource,
  getFilters
} from "./common.js";
import { buildRoute, monitorOptions, readRoute, updateRoute } from "./route.js";
import {
  zeroCoverageDisplay,
  zeroCoverageMenu
} from "./zero_coverage_report.js";
import "normalize.css/normalize.css";
import "./style.scss";
import Prism from "prismjs";
import Chartist from "chartist";
import "chartist/dist/chartist.css";

const VIEW_ZERO_COVERAGE = "zero";
const VIEW_DIRECTORY = "directory";
const VIEW_FILE = "file";

function browserMenu(revision, filters, route) {
  const context = {
    revision,
    platforms: filters.platforms.map(p => {
      return {
        name: p,
        selected: p === route.platform
      };
    }),
    suites: filters.suites.map(s => {
      return {
        name: s,
        selected: s === route.suite
      };
    })
  };
  render("menu_browser", context, "menu");
}

async function graphHistory(history, path) {
  if (history === null) {
    message("warning", `No history data for ${path}`);
    return;
  }

  const dateStr = function(timestamp) {
    const date = new Date(timestamp);
    return `${date.getDate()}/${date.getMonth() + 1}/${date.getFullYear()}`;
  };

  var data = {
    series: [
      {
        name: "History",
        data: history.map(push => {
          return {
            x: push.date * 1000,
            y: push.coverage
          };
        })
      }
    ]
  };
  var config = {
    // Display dates on a linear scale
    axisX: {
      type: Chartist.FixedScaleAxis,
      divisor: 20,
      labelInterpolationFnc: dateStr
    },

    // Fix display bug when points are too close
    lineSmooth: Chartist.Interpolation.cardinal({
      tension: 1
    })
  };
  const elt = show("history").querySelector(".ct-chart");
  const chart = new Chartist.Line(elt, data, config);

  chart.on("draw", function(evt) {
    if (evt.type === "point") {
      // Load revision from graph when a point is clicked
      const revision = history[evt.index].changeset;
      evt.element._node.onclick = function() {
        updateRoute({ revision });
      };

      // Display revision from graph when a point is overed
      evt.element._node.onmouseover = function() {
        const ctx = {
          revision: revision.substring(0, 12),
          date: dateStr(evt.value.x)
        };
        render("history_point", ctx, "history_details");
      };
    }
  });
}

async function showDirectory(dir, revision, files) {
  files.sort(function (file1, file2) {
    return file1.coveragePercent - file2.coveragePercent
  });
  const context = {
    navbar: buildNavbar(dir, revision),
    files: files.map(file => {
      file.route = buildRoute({
        path: file.path,
        view: file.type
      });

      // Calc decimal range to make a nice coloration
      file.coveragePercent = Math.floor(file.coveragePercent);
      file.range = parseInt(file.coveragePercent / 10) * 10;
      return file;
    }),
    revision: revision || REV_LATEST,
    file_name() {
      // Build filename relative to current dir
      return dir ? this.path.substring(dir.length + 1) : this.path;
    }
  };
  render("file_browser", context, "output");
}

async function showFile(source, file, revision, selectedLine) {
  selectedLine = selectedLine !== undefined ? parseInt(selectedLine) : -1;

  let language;
  if (file.path.endsWith("cpp") || file.path.endsWith("h")) {
    language = "cpp";
  } else if (file.path.endsWith("c")) {
    language = "c";
  } else if (file.path.endsWith("js") || file.path.endsWith("jsm")) {
    language = "javascript";
  } else if (file.path.endsWith("css")) {
    language = "css";
  } else if (file.path.endsWith("py")) {
    language = "python";
  } else if (file.path.endsWith("java")) {
    language = "java";
  }

  const context = {
    navbar: buildNavbar(file.path, revision),
    language,
    lines: source.map((line, nb) => {
      const coverage = file.coverage[nb];
      let cssClass = "";
      let hits = null;
      if (coverage !== undefined && coverage >= 0) {
        cssClass = coverage > 0 ? "covered" : "uncovered";

        // Build a nicer coverage string for counts
        if (coverage >= 1000000) {
          hits = {
            nb: parseInt(coverage / 1000000),
            unit: "M"
          };
        } else if (coverage >= 1000) {
          hits = {
            nb: parseInt(coverage / 1000),
            unit: "k"
          };
        } else if (coverage > 0) {
          hits = {
            nb: coverage,
            unit: ""
          };
        }
      }

      // Override css class when selected
      if (nb === selectedLine) {
        cssClass = "selected";
      }
      return {
        nb,
        hits,
        coverage,
        line: line || " ",
        css_class: cssClass,
        route: buildRoute({ line: nb })
      };
    })
  };

  hide("message");
  hide("history");
  const output = render("file_coverage", context, "output");

  // Scroll to line
  if (selectedLine > 0) {
    const line = output.querySelector("#l" + selectedLine);
    line.scrollIntoView({
      behavior: "smooth",
      block: "center"
    });
  }

  // Highlight source code once displayed
  Prism.highlightAll(output);
}

async function load() {
  const route = readRoute();

  // Reset display, dom-safe
  hide("history");
  hide("output");
  message(
    "loading",
    "Loading coverage data for " +
      (route.path || "mozilla-central") +
      " @ " +
      (route.revision || REV_LATEST)
  );

  // Load only zero coverage for that specific view
  if (route.view === VIEW_ZERO_COVERAGE) {
    const zeroCoverage = await getZeroCoverageData();
    return {
      view: VIEW_ZERO_COVERAGE,
      path: route.path,
      zeroCoverage,
      route
    };
  }

  // Default to directory view on home
  if (!route.view) {
    route.view = VIEW_DIRECTORY;
  }

  try {
    const viewContent =
      route.view === VIEW_DIRECTORY
        ? getHistory(route.path, route.platform, route.suite)
        : getSource(route.path, route.revision);
    var [coverage, filters, viewData] = await Promise.all([
      getPathCoverage(route.path, route.revision, route.platform, route.suite),
      getFilters(),
      viewContent
    ]);
  } catch (err) {
    console.warn("Failed to load coverage", err);
    await DOM_READY; // We want to always display this message
    message("error", "Failed to load coverage: " + err.message);
    throw err;
  }
  return {
    view: route.view,
    path: route.path,
    revision: route.revision,
    route,
    coverage,
    filters,
    viewData
  };
}

export async function display(data) {
  if (data.view === VIEW_ZERO_COVERAGE) {
    await zeroCoverageMenu(data.route);
    await zeroCoverageDisplay(data.zeroCoverage, data.path);
  } else if (data.view === VIEW_DIRECTORY) {
    hide("message");
    browserMenu(data.revision, data.filters, data.route);
    await graphHistory(data.viewData, data.path);
    await showDirectory(data.path, data.revision, data.coverage.children);
  } else if (data.view === VIEW_FILE) {
    browserMenu(data.revision, data.filters, data.route);
    await showFile(
      data.viewData,
      data.coverage,
      data.revision,
      data.route.line
    );
  } else {
    message("error", "Invalid view : " + data.view);
  }

  // Always monitor options on newly rendered output
  monitorOptions(data);
}

main(load, display);
