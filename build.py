import os
import zipfile

zip_file = 'gecko-code-coverage.zip'

try:
    os.remove(zip_file)
except FileNotFoundError:
    pass

files = [f for f in os.listdir('.') if os.path.isfile(f) and not f.endswith('.py')]
for f in ['.gitignore', 'LICENSE', 'README.md', 'package.json', 'package-lock.json']:
    files.remove(f)

with zipfile.ZipFile(zip_file, mode='w', compression=zipfile.ZIP_DEFLATED) as z:
    for f in files:
        z.write(f)
