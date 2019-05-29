'use strict';

const fs = require('fs');
const https = require('https');
const archiver = require('archiver');

const includeFiles = [
  'coverage.jpg', 'coverage.js',
  'button.js',
  'dxr.css', 'dxr.js', 'dxr-common.js',
  'manifest.json', 'searchfox.js',
  'socorro.js', 'socorro.css', 'codecov.png',
  'spinner.css', 'supported_extensions.js', 'hgmo.js'
];
const zipName = './gecko-code-coverage.zip';
fs.readFile('manifest.json', 'utf8', function(err, data) {
  if (err) throw err;
  let manObj = JSON.parse(data);
  fs.readFile('package.json', 'utf8', function(err, data) {
    if (err) throw err;
    let packObj = JSON.parse(data);
    if (manObj["version"] != packObj["version"]) {
      throw "Different versions of manifest.json and package.json";
    }
  });
});

https.get('https://coverage.moz.tools/coverage/supported_extensions', res => {
  let data = '';
    
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    let content = `const SUPPORTED_EXTENSIONS = ${data};`;

    fs.writeFile('supported_extensions.js', content, e => {
      if (e) {
        throw e;
      }

      fs.readdir('.', (e, files) => {
        if (e) {
          throw e;
        }

        const resultFiles = files.filter(file => includeFiles.includes(file));

        makeZip(resultFiles);
      });
    });
  });
}).on('error', e => { throw e; });

function makeZip(list){
  const output = fs.createWriteStream(zipName);

  let archive = archiver('zip', {
    zlib: { level: 9 }
  });

  archive.on('error', e => { throw e; });

  archive.pipe(output);

  list.forEach(file => archive.file(file));

  archive.finalize();
}
