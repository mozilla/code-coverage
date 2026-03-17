from taskgraph.transforms.base import TransformSequence

transforms = TransformSequence()


@transforms.add
def add_release_config(config, tasks):
    for task in tasks:
        params = config.params
        version = params["head_ref"]
        is_level_3 = params["level"] == "3"

        task.setdefault("worker", {})
        command = ["taskboot", "github-release", "mozilla/code-coverage", version]
        if not is_level_3:
            command.append("--dry-run")
        task["worker"]["command"] = command

        if is_level_3:
            task["worker"].setdefault("env", {})["TASKCLUSTER_SECRET"] = (
                "project/relman/code-coverage/release"
            )
            task.setdefault("scopes", []).append(
                "secrets:get:project/relman/code-coverage/release"
            )

        yield task
