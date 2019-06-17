function getSpanForFile(data, dir) {
  const span = document.createElement('span');
  span.className = 'filename';
  const a = document.createElement('a');
  a.textContent = data.path.substring(dir.length);
  a.href = '#' + data.path;
  span.appendChild(a);
  return span;
}

function graphHistory(path) {
  // Backend needs path without ending /
  if (path && path.endsWith('/')) {
    path = path.substring(0, path.length-1);
  }

  get_history(path).then(function(data){
    var trace = {
      x: data.map(push => new Date(push.date * 1000)),
      y: data.map(push => push.coverage),
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Coverage %'
    };

    var layout = {
      title:'Coverage history for ' + (path || 'full repository')
    };

    Plotly.newPlot('history', [ trace ], layout);
  });
}

async function showDirectory(dir, files) {
  files = await filter_third_party(files);
  files = filter_languages(files);

  const columns = [['File name', x => getSpanForFile(x, dir)],
                   ['Children', x => getSpanForValue(x.children)],
                   ['Coverage', x => getSpanForValue(x.coveragePercent + ' %')]];

  const output = document.createElement('div');
  output.id = 'output';

  const global = document.createElement('div');
  global.textContent = files.length + ' files';
  output.appendChild(global);
  output.appendChild(document.createElement('br'));
  output.appendChild(document.createElement('br'));

  const header = document.createElement('div');
  header.className = 'header';
  columns.forEach(([name, ]) => {
    const span = getSpanForValue(name);
    if (name === 'File name') {
      span.className = 'filename';
    }
    header.append(span);
  });
  output.append(header);

  for (const file of files) {
    const entryElem = document.createElement('div');
    entryElem.className = 'row';
    columns.forEach(([, func]) => {
      entryElem.append(func(file));
    });
    output.appendChild(entryElem);
  }
  document.getElementById('output').replaceWith(output);

  graphHistory(dir);
}

async function showFile(file) {
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
  const coverage = await get_path_coverage(file.path);

  const table = document.createElement('table');
  table.id = 'output';
  table.style.borderCollapse = 'collapse';
  table.style.borderSpacing = 0;
  const tbody = document.createElement('tbody');
  tbody.style.border = 'none';
  table.appendChild(tbody);

  for (let [lineNumber, lineText] of source.split('\n').entries()) {
    const tr = document.createElement('tr');
    tbody.appendChild(tr);

    const lineNumberTd = document.createElement('td');
    lineNumberTd.style.padding = 0;
    lineNumberTd.textContent = lineNumber;
    tr.appendChild(lineNumberTd);

    const lineTextTd = document.createElement('td');
    lineTextTd.style.padding = 0;
    const pre = document.createElement('pre');
    pre.style.margin = 0;
    pre.style.padding = 0;
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

    if (coverage['coverage'][lineNumber] != -1) {
      if (coverage['coverage'][lineNumber] > 0) {
        pre.style.backgroundColor = lineNumberTd.style.backgroundColor = 'palegreen';
      } else {
        pre.style.backgroundColor = lineNumberTd.style.backgroundColor = 'coral';
      }
    }
  }

  document.getElementById('output').replaceWith(table);

  /*const pre = document.createElement('pre');
  const code = document.createElement('code');
  pre.appendChild(code);
  pre.classList.add('lang-cpp');
  pre.classList.add('line-numbers');

  code.textContent = source;

  await new Promise(resolve => Prism.highlightElement(pre, true, resolve));

  document.getElementById('output').replaceWith(pre);*/
}

async function generate() {
  const path = window.location.hash.substring(1);
  console.log(path);

  const data = await get_path_coverage(path);
  console.log(data);

  if (data.type == 'directory') {
    await showDirectory(path, data.children);
  } else if (data.type === 'file') {
    await showFile(data);
  }
}

main(generate, ['third_party', 'cpp', 'js', 'java', 'rust']);
