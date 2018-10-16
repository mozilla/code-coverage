function assert(condition, message) {
  if (!condition) {
    throw new Error(message || "Assertion failed");
  }
}

const COVERAGE_BACKEND_HOST = 'https://coverage.testing.moz.tools';

async function get_data(path) {
  let response = await fetch(`${COVERAGE_BACKEND_HOST}/v2/path?path=${path}`);
  return await response.json();
}

async function get_latest() {
  let response = await fetch(`${COVERAGE_BACKEND_HOST}/coverage/latest`);
  return (await response.json())['latest_rev'];
}

async function get_file_coverage(changeset, path) {
  let response = await fetch(`${COVERAGE_BACKEND_HOST}/coverage/file?changeset=${changeset}&path=${path}`);
  return await response.json();
}

let get_third_party_paths = function() {
  let paths = null;
  return async function() {
    if (!paths) {
      let response = await getSource('tools/rewriting/ThirdPartyPaths.txt');
      paths = response.split('\n').filter(path => path != '');
    }

    return paths;
  };
}();

function is_enabled(opt) {
  let elem = document.getElementById(opt);
  return elem.checked;
}

async function filter_third_party(files) {
  if (is_enabled('third_party')) {
    return files;
  }

  let paths = await get_third_party_paths();

  return files.filter(file => {
    for (let path of paths) {
      if (file.name.startsWith(path)) {
        return false;
      }
    }

    return true;
  });
}

function filter_languages(files) {
  let cpp = is_enabled('cpp');
  let cpp_extensions = ['c', 'cpp', 'cxx', 'cc', 'h', 'hh', 'hxx', 'hpp', 'inl', 'inc'];
  let js = is_enabled('js');
  let js_extensions = ['js', 'jsm', 'xml', 'xul', 'xhtml', 'html'];
  let java = is_enabled('java');
  let java_extensions = ['java'];

  return files.filter(file => {
    if (file.path.endsWith('/')) {
      return true;
    } else if (cpp_extensions.find(ext => file.path.endsWith('.' + ext))) {
      return cpp;
    } else if (js_extensions.find(ext => file.path.endsWith('.' + ext))) {
      return js;
    } else if (java_extensions.find(ext => file.path.endsWith('.' + ext))) {
      return java;
    } else {
      console.warn('Unknown language for ' + file.path);
      return false;
    }
  });
}

function getSpanForValue(value) {
  const span = document.createElement('span');
  span.innerText = value == 0 ? '' : value;
  return span;
}

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

async function getSource(file) {
  let response = await fetch(`https://hg.mozilla.org/mozilla-central/raw-file/tip/${file}`);
  return await response.text();
}

async function showFile(file) {
  let source = await getSource(file.path);

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
  const data = await get_data(path);
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
