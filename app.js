function sort_entries(entries) {
  return entries.sort(([dir1, stats1], [dir2, stats2]) => {
    if (stats1.children != stats2.children) {
      return stats1.children < stats2.children;
    }

    if (stats1.funcs != stats2.funcs) {
      return stats1.funcs < stats2.funcs;
    }

    return dir1 > dir2;
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
  return {'children': children,
          'funcs': file.funcs,
          'first_push_date': file.first_push_date,
          'last_push_date': file.last_push_date,
          'size': file.size,
          'commits': file.commits};
}

function cumStats(prevStats, newStats) {
  prevStats.children += 1;
  prevStats.funcs += newStats.funcs;
  prevStats.size += newStats.size;
  prevStats.commits += newStats.commits;
  prevStats.first_push_date = get_min_date(prevStats.first_push_date, newStats.first_push_date);
  prevStats.last_push_date = get_min_date(prevStats.last_push_date, newStats.last_push_date);
}

function getSpanForFile(data, github_rev, dir, entry) {
  const span = document.createElement('span');
  span.className = 'filename';
  const a = document.createElement('a');
  a.textContent = entry;
  const path = dir + entry;
  if (data.children != 0) {
    a.href = '#' + path;
  } else {
    a.target = '_blank';
    const rev = github_rev ? github_rev : 'master';
    a.href = `https://codecov.io/gh/mozilla/gecko-dev/src/${rev}/${path}`;
  }
  span.appendChild(a);
  return span;
}

function getFileSize(size) {
  if (size >= 1e6) {
    return (size / 1e6).toFixed(2) + 'M';
  } else if (size >= 1e3) {
    return (size / 1e3).toFixed(1) + 'K';
  }
  return size;
}

async function generate() {
  let dir = window.location.hash.substring(1);

  while (dir.endsWith('/')) dir = dir.substring(0, dir.length - 1);
  dir += '/';
  if (dir == '/') {
    dir = '';
  }

  const data = await get_zero_coverage_data();
  const github_revision = data['github_revision'];
  let files = data['files'].filter(file => file.name.startsWith(dir));
  // TODO: Do this in the backend directly!
  files.forEach(file => {
    file.path = file.name;
  });
  files = await filter_third_party(files);
  files = filter_languages(files);
  files = filter_headers(files);
  files = filter_completely_uncovered(files);
  files = filter_last_push_date(files);

  let map = new Map();

  for (let file of files) {
    let rest = file.path.substring(dir.lastIndexOf('/') + 1);

    if (rest.includes('/')) {
      rest = rest.substring(0, rest.indexOf('/'));
      if (map.has(rest)) {
        cumStats(map.get(rest), file);
      } else {
        map.set(rest, getBaseStats(file, 1));
      }
    } else {
      if (map.has(rest)) {
        console.warn(rest + ' is already in map.');
      }
      map.set(rest, getBaseStats(file, 0));
    }
  }

  const columns = [['File name', (x, dir, entry) => getSpanForFile(x, github_revision, dir, entry)],
                   ['Children', (x) => getSpanForValue(x.children)],
                   ['Functions', (x) => getSpanForValue(x.funcs)],
                   ['First push', (x) => getSpanForValue(x.first_push_date)],
                   ['Last push', (x) => getSpanForValue(x.last_push_date)],
                   ['Size', (x) => getSpanForValue(getFileSize(x.size))],
                   ['Commits', (x) => getSpanForValue(x.commits)]];

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

  for (const [entry, stats] of sort_entries(Array.from(map.entries()))) {
    const entryElem = document.createElement('div');
    entryElem.className = 'row';
    columns.forEach(([, func]) => {
      entryElem.append(func(stats, dir, entry));
    });
    output.appendChild(entryElem);
  }
  document.getElementById('output').replaceWith(output);
}

main(generate, ['third_party', 'headers', 'completely_uncovered', 'cpp', 'js', 'java', 'rust', 'last_push']);
