function sort_entries(entries) {
  return entries.sort(([dir1, stats1], [dir2, stats2]) => {
    if (stats1.children != stats2.children) {
      return stats1.children < stats2.children;
    }

    if (stats1.funcs != stats2.funcs) {
      return stats1.funcs < stats2.funcs;
    }

    return dir1 > dir2;
  }).map(([dir , stats]) => {
    return {stats, dir};
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

function getFileSize(size) {
  if (size >= 1e6) {
    return (size / 1e6).toFixed(2) + 'M';
  } else if (size >= 1e3) {
    return (size / 1e3).toFixed(1) + 'K';
  }
  return size;
}

async function display(data) {
  let dir = window.location.hash.substring(1);

  hide('output');
  message('loading', 'Loading zero coverage report for ' + (dir || 'mozilla-central'));

  while (dir.endsWith('/')) dir = dir.substring(0, dir.length - 1);
  dir += '/';
  if (dir == '/') {
    dir = '';
  }

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

  const revision = data['hg_revision'];
  let context = {
    current_dir: dir,
    entries: sort_entries(Array.from(map.entries())),
    entry_url : function() {
      let path = dir + this.dir;
      if (this.stats.children != 0) {
        return `#${path}`;
      } else {
        return `./index.html#${revision}:${path}`;
      }
    },
    navbar: build_navbar(dir),
    total: files.length,
  };

  hide('message');
  render('zerocoverage', context, 'output');
}

main(get_zero_coverage_data, display, ['third_party', 'headers', 'completely_uncovered', 'cpp', 'js', 'java', 'rust', 'last_push']);
