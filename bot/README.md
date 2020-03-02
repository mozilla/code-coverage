# Code Coverage Bot

This project runs as [Taskcluster hooks](https://firefox-ci-tc.services.mozilla.com/hooks) on the firefox-ci instance, to extract and store the code coverage information from mozilla-central and try builds.

It's built using Python 3.8 and few dependencies.

## Developer setup

Requirements:

- Python 3.8
- [virtualenv](https://virtualenv.pypa.io/en/stable/)
- [virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/en/latest/)
- Mercurial 5.3

Setup on your computer:

```console
mkvirtualenv -p /usr/bin/python3.8 code-coverage-bot
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
pre-commit install
```

Check linting (it should be automatically done before any commit):

```console
pre-commint run -a
```

Check unit tests:

```console
pytest -v
```

Write your local configuration as YAML:

```yaml
---
common:
  APP_CHANNEL: dev
bot:
  BACKEND_HOST: 'http://localhost:8000'
  EMAIL_ADDRESSES: []
  PHABRICATOR_TOKEN: api-xxx
  PHABRICATOR_ENABLED: false
  PHABRICATOR_URL: 'https://phabricator-dev.allizom.org/api/'
	GOOGLE_CLOUD_STORAGE: null
```

Run the bot (in cron mode):

```console
mkdir -p build/{cache,work} # or elsewhere on your system
code-coverage-cron--cache-root=build/cache --working-dir=build/work --local-configuration=path/to/code-coverage.yml
```

The repo mode (with `code-coverage-repo` is harder to use, as it requires a Google Cloud Storage & Phabricator account.

## Help

You can reach us on our Matrix instance: [#codecoverage:mozilla.org](https://chat.mozilla.org/#/room/#codecoverage:mozilla.org)
