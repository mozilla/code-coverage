from taskgraph.transforms.base import TransformSequence

transforms = TransformSequence()


@transforms.add
def add_release_config(config, tasks):
    for task in tasks:
        params = config.params
        version = params["head_ref"]

        task.setdefault("worker", {})
        task["worker"]["command"] = [
            "taskboot",
            "github-release",
            "mozilla/code-coverage",
            version,
        ]
        task["worker"].setdefault("env", {})["TASKCLUSTER_SECRET"] = (
            "project/relman/code-coverage/release"
        )

        yield task
