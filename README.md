# Mozilla Code Coverage

This project has 4 parts:

* `bot` is a Python script running as a Taskcluster hook, aggregating code coverage data from Mozilla repositories,
* `backend` is a Python API built with Flask, that serves the aggregated code coverage data, in an efficient way,
* `frontend` is a vanilla Javascript SPA displaying code coverage data in your browser,
* `addon` is a Web Extension for Firefox, extending several Mozilla websites with code coverage data. Published at https://addons.mozilla.org/firefox/addon/gecko-code-coverage/.

## Help

You can reach us on our Matrix instance: [#codecoverage:mozilla.org](https://chat.mozilla.org/#/room/#codecoverage:mozilla.org)

## Thunderbird Changes

Note: The system running the container must be supplied with at least 16gb of memory. Other-wise you will run into out of memory killer issues while grcov runs.

This fork contains some Thunderbird specific changes:

* Zero coverage reports are uploaded to Google Cloud Storage, and pulled down by the backend api.
* A Thunderbird Cron file has been added, that pulls down comm-central's tip revision and generates all reports.
* The frontend has been removed from `.dockerignore`, and runs in a docker container for deployment purposes.
* Various tweaks to allow a repository that isn't mozilla-central to generate reports (these changes are also available on `multi-repo` branch.)
