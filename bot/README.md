# Code Coverage Bot

This project runs as [Taskcluster hooks](https://firefox-ci-tc.services.mozilla.com/hooks) on the firefox-ci instance, to extract and store the code coverage information from mozilla-central and try builds.

It's built using Python 3.14 and few dependencies, managed with the repository's [uv](https://docs.astral.sh/uv/) workspace.

## Developer setup

Requirements:

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Mercurial 7.2

Setup on your computer, from the repository root:

```console
uv sync
uv run pre-commit install
```

Check linting (it should be automatically done before any commit):

```console
uv run pre-commit run -a
```

Check unit tests:

```console
uv run pytest -v
```

Write your local configuration as YAML:

```yaml
---
common:
  APP_CHANNEL: dev
bot:
  EMAIL_ADDRESSES: []
  PHABRICATOR_TOKEN: api-xxx
  PHABRICATOR_ENABLED: false
  PHABRICATOR_URL: "https://phabricator-dev.allizom.org/api/"
  GOOGLE_CLOUD_STORAGE: null
```

Run the bot (in cron mode):

```console
mkdir -p build/{cache,work} # or elsewhere on your system
uv run code-coverage-cron --cache-root=build/cache --working-dir=build/work --local-configuration=path/to/code-coverage.yml
```

The repo mode (with `code-coverage-repo`) is harder to use, as it requires a Google Cloud Storage and a Phabricator account.

## Help

You can reach us on our Matrix instance: [#codecoverage:mozilla.org](https://chat.mozilla.org/#/room/#codecoverage:mozilla.org)
