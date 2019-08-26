import {REV_LATEST, DOM_READY, main, show, hide, message, getPathCoverage, getHistory,
  getZeroCoverageData, buildNavbar, render, getSource, getFilters} from './common.js';
import {buildRoute, readRoute, updateRoute} from './route.js';
import {zeroCoverageDisplay, zeroCoverageMenu} from './zero_coverage_report.js';
import './style.css';
import Prism from 'prismjs';
import Chartist from 'chartist';
import 'chartist/dist/chartist.css';

const VIEW_ZERO_COVERAGE = 'zero';
const VIEW_BROWSER = 'browser';


function browserMenu(revision, filters, route) {
  const context = {
    revision,
    platforms: filters.platforms.map((p) => {
      return {
        'name': p,
        'selected': p == route.platform,
      };
    }),
    suites: filters.suites.map((s) => {
      return {
        'name': s,
        'selected': s == route.suite,
      };
    }),
  };
  render('menu_browser', context, 'menu');
}

async function graphHistory(history, path) {
  if (history === null) {
    message('warning', `No history data for ${path}`);
    return;
  }

  const dateStr = function(timestamp) {
    const date = new Date(timestamp);
    return `${date.getDate()}/${date.getMonth() + 1}/${date.getFullYear()}`;
  };

  const data = {
    series: [
      {
        name: 'History',
        data: history.map((push) => {
          return {
            x: push.date * 1000,
            y: push.coverage,
          };
        }),
      },
    ],
  };
  const config = {
    // Display dates on a linear scale
    axisX: {
      type: Chartist.FixedScaleAxis,
      divisor: 20,
      labelInterpolationFnc: dateStr,
    },

    // Fix display bug when points are too close
    lineSmooth: Chartist.Interpolation.cardinal({
      tension: 1,
    }),
  };
  const elt = show('history').querySelector('.ct-chart');
  const chart = new Chartist.Line(elt, data, config);

  chart.on('draw', function(evt) {
    if (evt.type === 'point') {
      // Load revision from graph when a point is clicked
      const revision = history[evt.index].changeset;
      evt.element._node.onclick = function() {
        updateRoute({revision});
      };

      // Display revision from graph when a point is overed
      evt.element._node.onmouseover = function() {
        const ctx = {
          revision: revision.substring(0, 12),
          date: dateStr(evt.value.x),
        };
        render('history_point', ctx, 'history_details');
      };
    }
  });
}

async function showDirectory(dir, revision, files) {
  const context = {
    navbar: buildNavbar(dir, revision),
    files: files.map((file) => {
      file.route = buildRoute({
        path: file.path,
      });
      return file;
    }),
    revision: revision || REV_LATEST,
    file_name: function() {
      // Build filename relative to current dir
      return dir ? this.path.substring(dir.length+1) : this.path;
    },
  };
  render('browser', context, 'output');
}

async function showFile(file, revision) {
  const source = await getSource(file.path);

  let language;
  if (file.path.endsWith('cpp') || file.path.endsWith('h')) {
    language = 'cpp';
  } else if (file.path.endsWith('c')) {
    language = 'c';
  } else if (file.path.endsWith('js') || file.path.endsWith('jsm')) {
    language = 'javascript';
  } else if (file.path.endsWith('css')) {
    language = 'css';
  } else if (file.path.endsWith('py')) {
    language = 'python';
  } else if (file.path.endsWith('java')) {
    language = 'java';
  }

  const context = {
    navbar: buildNavbar(file.path, revision),
    revision: revision || REV_LATEST,
    language: language,
    lines: source.split('\n').map((line, nb) => {
      const coverage = file.coverage[nb];
      let cssClass = '';
      if (coverage !== -1) {
        cssClass = coverage > 0 ? 'covered': 'uncovered';
      }
      return {
        nb: nb,
        line: line || ' ',
        covered: cssClass,
      };
    }),
  };

  hide('message');
  hide('history');
  const output = render('file_coverage', context, 'output');

  // Highlight source code once displayed
  Prism.highlightAll(output);
}

async function load() {
  const route = readRoute();

  // Reset display, dom-safe
  hide('history');
  hide('output');
  message('loading', 'Loading coverage data for ' + (route.path || 'mozilla-central') + ' @ ' + route.revision);

  // Load only zero coverage for that specific view
  if (route.view === VIEW_ZERO_COVERAGE) {
    const zeroCoverage = await getZeroCoverageData();
    return {
      view: VIEW_ZERO_COVERAGE,
      path: route.path,
      zeroCoverage,
      route,
    };
  }

  try {
    const [coverage, history, filters] = await Promise.all([
      getPathCoverage(route.path, route.revision, route.platform, route.suite),
      getHistory(route.path, route.platform, route.suite),
      getFilters(),
    ]);

    return {
      view: VIEW_BROWSER,
      path: route.path,
      revision: route.revision,
      route,
      coverage,
      history,
      filters,
    };
  } catch (err) {
    console.warn('Failed to load coverage', err);
    await DOM_READY; // We want to always display this message
    message('error', 'Failed to load coverage: ' + err.message);
    throw err;
  }
}

async function display(data) {
  if (data.view === VIEW_ZERO_COVERAGE ) {
    await zeroCoverageMenu(data.route);
    await zeroCoverageDisplay(data.zeroCoverage, data.path);
  } else if (data.view === VIEW_BROWSER) {
    browserMenu(data.revision, data.filters, data.route);

    if (data.coverage.type === 'directory') {
      hide('message');
      await graphHistory(data.history, data.path);
      await showDirectory(data.path, data.revision, data.coverage.children);
    } else if (data.coverage.type === 'file') {
      await showFile(data.coverage, data.revision);
    } else {
      message('error', 'Invalid file type: ' + data.coverate.type);
    }
  } else {
    message('error', 'Invalid view : ' + data.view);
  }
}

main(load, display);
