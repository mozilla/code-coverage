import os
import zipfile

import requests


zip_file = 'gecko-code-coverage.zip'

try:
    os.remove(zip_file)
except FileNotFoundError:
    pass

r = requests.get('https://uplift.shipit.staging.mozilla-releng.net/coverage/supported_extensions')
r.raise_for_status()
with open('supported_extensions.js', 'w') as f:
    f.write('const SUPPORTED_EXTENSIONS = {};'.format(r.text.rstrip('\n')))

files = [f for f in os.listdir('.') if os.path.isfile(f) and not f.endswith('.py')]
for f in ['.gitignore', '.travis.yml', 'LICENSE', 'README.md', 'package.json', 'package-lock.json']:
    files.remove(f)

with zipfile.ZipFile(zip_file, mode='w', compression=zipfile.ZIP_DEFLATED) as z:
    for f in files:
        z.write(f)
