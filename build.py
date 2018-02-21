import os
import zipfile

try:
    os.remove('gecko-coverage-addon.zip')
except FileNotFoundError:
    pass

files = [f for f in os.listdir('.') if os.path.isfile(f) and not f.endswith('.py')]
files.remove('LICENSE')
files.remove('README.md')

with zipfile.ZipFile('gecko-coverage-addon.zip', mode='w', compression=zipfile.ZIP_DEFLATED) as z:
    for f in files:
        z.write(f)
