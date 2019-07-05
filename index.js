function getSpanForFile(data, dir, revision) {
  const span = document.createElement('span');
  span.className = 'filename';
  const a = document.createElement('a');
  a.textContent = dir ? data.path.substring(dir.length+1) : data.path;
  a.href = '#' + (revision || REV_LATEST) + ':' + data.path;
  span.appendChild(a);
  return span;
}

async function graphHistory(path) {
  // Backend needs path without ending /
  if (path && path.endsWith('/')) {
    path = path.substring(0, path.length-1);
  }

  try {
    var data = await get_history(path);
  } catch (err) {
    message('warning', err.message);
    return;
  }

  let trace = {
    x: data.map(push => new Date(push.date * 1000)),
    y: data.map(push => push.coverage),
    type: 'scatter',
    mode: 'lines+markers',
    name: 'Coverage %'
  };

  let layout = {
    title:'Coverage history for ' + (path || 'mozilla-central')
  };

  show('history');
  Plotly.newPlot('history', [ trace ], layout);
}

async function showDirectory(dir, revision, files) {
  graphHistory(dir);

  const columns = [['File name', x => getSpanForFile(x, dir, revision)],
                   ['Children', x => getSpanForValue(x.children)],
                   ['Coverage', x => getSpanForValue(x.coveragePercent + ' %')]];

  const output = document.createElement('div');
  output.id = 'output';
  output.className = 'directory';

  // Create menu with navbar
  const menu = document.createElement('h2');
  menu.appendChild(navbar(dir, revision));
  let title = document.createElement('span');
  title.textContent = ': ' + files.length + ' directories/files';
  menu.appendChild(title)
  output.appendChild(menu);

  const table = document.createElement('div');
  table.className = 'table';

  const header = document.createElement('div');
  header.className = 'header';
  columns.forEach(([name, ]) => {
    const span = getSpanForValue(name);
    if (name === 'File name') {
      span.className = 'filename';
    }
    header.append(span);
  });
  table.append(header);

  for (const file of files) {
    const entryElem = document.createElement('div');
    entryElem.className = 'row';
    columns.forEach(([, func]) => {
      entryElem.append(func(file));
    });
    table.appendChild(entryElem);
  }
  output.appendChild(table);
  hide('message');
  show('output', output);
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

  const changeset = await get_latest();

  const output = document.createElement('div');
  output.id = 'output';
  output.className = 'file';
  output.appendChild(navbar(file.path, revision));

  const table = document.createElement('table');
  table.id = 'file';
  table.style.borderCollapse = 'collapse';
  table.style.borderSpacing = 0;
  const tbody = document.createElement('tbody');
  tbody.style.border = 'none';
  table.appendChild(tbody);

  for (let [lineNumber, lineText] of source.split('\n').entries()) {
    const tr = document.createElement('tr');
    tbody.appendChild(tr);

    const lineNumberTd = document.createElement('td');
    lineNumberTd.textContent = lineNumber;
    tr.appendChild(lineNumberTd);

    const lineTextTd = document.createElement('td');
    const pre = document.createElement('pre');
    const code = document.createElement('code');
    pre.appendChild(code);
    lineTextTd.appendChild(pre);
    tr.appendChild(lineTextTd);

    if (lineText) {
      code.textContent = lineText;
    } else {
      code.textContent = ' ';
    }

    code.classList.add(`lang-${language}`);
    Prism.highlightElement(code);

    if (file.coverage[lineNumber] != -1) {
      let cssClass = (file.coverage[lineNumber] > 0) ? 'covered' : 'uncovered';
      tr.classList.add(cssClass);
    }
  }

  output.appendChild(table);
  hide('message');
  show('output', output);

  /*const pre = document.createElement('pre');
  const code = document.createElement('code');
  pre.appendChild(code);
  pre.classList.add('lang-cpp');
  pre.classList.add('line-numbers');

  code.textContent = source;

  await new Promise(resolve => Prism.highlightElement(pre, true, resolve));

  document.getElementById('output').replaceWith(pre);*/
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

async function generate() {
  let [revision, path] = readHash();

  // Reset display
  hide('history');
  hide('output');
  message('loading', 'Loading coverage data for ' + (path || 'mozilla-central') + ' @ ' + (revision || REV_LATEST));

  // Also update the revision element
  if (revision != REV_LATEST) {
    let input = document.getElementById('revision');
    input.value = revision;
  }

  try {
    var data = await get_path_coverage(path, revision);
  } catch (err) {
    message('error', 'Failed to load coverage: ' + err.message);
    return;
  }

  if (data.type == 'directory') {
    await showDirectory(path, revision, data.children);
  } else if (data.type === 'file') {
    await showFile(data, revision);
  }
}

async function workflow() {

  // Revision input management
  const revision = document.getElementById('revision');
  revision.onkeydown = async function(evt){
    if(evt.keyCode === 13) {
      updateHash(revision.value);
    }
  };

  // Default generation with latest data
  await generate();
};

main(workflow, []);
