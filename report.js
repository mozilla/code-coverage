function getSpanForFile(data, dir) {
  const span = document.createElement('span');
  span.className = 'filename';
  const a = document.createElement('a');
  a.textContent = data.path.substring(dir.length);
  a.href = '#' + data.path;
  span.appendChild(a);
  return span;
}

async function showDirectory(dir, files) {
  files = await filter_third_party(files);
  files = filter_languages(files);

  const columns = [['File name', x => getSpanForFile(x, dir)],
                   ['Children', x => getSpanForValue(x.nb)],
                   ['Coverage', x => getSpanForValue((x.coverage * 100).toFixed(1) + ' %')]];

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
  const coverage = await get_file_coverage(changeset, file.path);

  const table = document.createElement('table');
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

    if (coverage['data'].hasOwnProperty(lineNumber)) {
      if (coverage['data'][lineNumber] > 0) {
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

async function generate(path='') {
  /*while (dir.endsWith('/')) dir = dir.substring(0, dir.length - 1);
  dir += '/';
  if (dir == '/') {
    dir = '';
  }*/

  console.log(path);
  const data = await get_path_coverage(path);
  console.log(data);
  if (data.type == 'directory') {
    await showDirectory(path, data.children);
  } else if (data.type === 'file') {
    await showFile(data);
  }
}

async function main() {
  await new Promise(resolve => window.onload = resolve);

  function go() {
    generate(window.location.hash.substring(1));
  }

  let opts = ['third_party', 'cpp', 'js', 'java'];
  for (let opt of opts) {
    let elem = document.getElementById(opt);
    elem.onchange = go;
  }

  window.onhashchange = go;

  go();
}

main();
