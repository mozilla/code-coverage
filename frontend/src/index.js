import {REV_LATEST, DOM_READY, main, show, hide, message, get_path_coverage, get_history, get_zero_coverage_data, build_navbar, render, get_source} from './common.js';
import {zero_coverage_display} from './zero_coverage_report.js';
import './style.css';
import Prism from 'prismjs';
import Chartist from 'chartist';
import 'chartist/dist/chartist.css';

const VIEW_ZERO_COVERAGE = 'zero';
const VIEW_BROWSER = 'browser';

async function graphHistory(history, path) {
  if (history === null) {
    message('warning', `No history data for ${path}`);
    return;
  }

  let dateStr = function(timestamp){
    let date = new Date(timestamp);
    let month = date.getMonth() + 1;
    return date.getDate() + '/' + month + '/' + date.getFullYear();
  }

  var data = {
    series: [
      {
        name: 'History',
        data: history.map(push => {
          return {
            x: push.date * 1000,
            y: push.coverage,
          }
        })
      }
    ],
  };
  var config = {
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
  let elt = show('history').querySelector('.ct-chart');
  let chart = new Chartist.Line(elt, data, config);

  chart.on('draw', function(evt) {
    if(evt.type === 'point') {
      // Load revision from graph when a point is clicked
      let revision = history[evt.index].changeset;
      evt.element._node.onclick = function(){
        updateHash(revision, path);
      };

      // Display revision from graph when a point is overed
      evt.element._node.onmouseover = function(){
        let ctx = {
          revision: revision.substring(0, 12),
          date: dateStr(evt.value.x),
        };
        render('history_point', ctx, 'history_details');
      };
    }
  });
}

async function showDirectory(dir, revision, files) {
  let context = {
    navbar: build_navbar(dir, revision),
    files: files,
    revision: revision || REV_LATEST,
    file_name: function(){
      // Build filename relative to current dir
      return dir ? this.path.substring(dir.length+1) : this.path;
    }
  };
  render('browser', context, 'output');
}

async function showFile(file, revision) {
  let source = await get_source(file.path);

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

  let context = {
    navbar: build_navbar(file.path, revision),
    revision: revision || REV_LATEST,
    language: language,
    lines: source.split('\n').map((line, nb) => {
      let coverage = file.coverage[nb];
      let css_class = '';
      if (coverage !== -1) {
        css_class = coverage > 0 ? 'covered': 'uncovered';
      }
      return {
        nb: nb,
        line: line || ' ',
        covered: css_class,
      }
    }),
  };

  hide('message');
  hide('history');
  let output = render('file_coverage', context, 'output');

  // Highlight source code once displayed
  Prism.highlightAll(output);
}

function readHash() {
  // Reads changeset & path from current URL hash
  let hash = window.location.hash.substring(1);
  let pos = hash.indexOf(':');
  if (pos === -1) {
    return ['', ''];
  }
  return [
    hash.substring(0, pos),
    hash.substring(pos+1),
  ]
}

function updateHash(newChangeset, newPath) {
  // Set the URL hash with both changeset & path
  let [changeset, path] = readHash();
  changeset = newChangeset || changeset || REV_LATEST;
  path = newPath || path || '';
  window.location.hash = '#' + changeset + ':' + path;
}

async function load() {
  let [revision, path] = readHash();

  // Reset display, dom-safe
  hide('history');
  hide('output');
  message('loading', 'Loading coverage data for ' + (path || 'mozilla-central') + ' @ ' + (revision || REV_LATEST));

  // Load only zero coverage for that specific view
  if (revision === VIEW_ZERO_COVERAGE) {
    let zero_coverage = await get_zero_coverage_data();
    return {
      view: VIEW_ZERO_COVERAGE,
      path,
      zero_coverage,
    }
  }

  try {
    var [coverage, history] = await Promise.all([
      get_path_coverage(path, revision),
      get_history(path),
    ]);
  } catch (err) {
    console.warn('Failed to load coverage', err);
    await DOM_READY; // We want to always display this message
    message('error', 'Failed to load coverage: ' + err.message);
    throw err;
  }

  return {
    view: VIEW_BROWSER,
    path,
    revision,
    coverage,
    history,
  };
}

async function display(data) {

  // Toggle menu per views
  if (data.view === VIEW_BROWSER) {
    show('menu_browser');
    hide('menu_zero');
  } else if (data.view === VIEW_ZERO_COVERAGE) {
    show('menu_zero');
    hide('menu_browser');
  } else {
    message('error', 'Invalid view : ' + data.view);
  }

  // Revision input management
  const revision = document.getElementById('revision');
  revision.onkeydown = async function(evt){
    if(evt.keyCode === 13) {
      updateHash(data.revision.value);
    }
  };

  // Also update the revision element
  if (data.revision && data.revision != REV_LATEST) {
    let input = document.getElementById('revision');
    input.value = data.revision;
  }

  if (data.view === VIEW_ZERO_COVERAGE ) {
    await zero_coverage_display(data.zero_coverage, data.path);

  } else if (data.view === VIEW_BROWSER && data.coverage.type === 'directory') {
    hide('message');
    await graphHistory(data.history, data.path);
    await showDirectory(data.path, data.revision, data.coverage.children);

  } else if (data.view === VIEW_BROWSER && data.coverage.type === 'file') {
    await showFile(data.coverage, data.revision);

  } else {
    message('error', 'Invalid file type: ' + data.coverage.type);
  }
}

main(load, display, ['third_party', 'headers', 'completely_uncovered', 'cpp', 'js', 'java', 'rust', 'last_push'])
