# Mozilla Code Coverage
-------------------------------
* This project has 4 parts:

* `BOT` is a Python script running as a Taskcluster hook, aggregating code coverage data from Mozilla repositories,
* `BACKENED` is a Python API built with Flask, that serves the aggregated code coverage data, in an efficient way,
* `FRONTEND` is a vanilla Javascript SPA displaying code coverage data in your browser,
* `ADDON` is a Web Extension for Firefox, extending several Mozilla websites with code coverage data.
