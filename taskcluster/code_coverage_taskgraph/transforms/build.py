from taskgraph.transforms.base import TransformSequence

transforms = TransformSequence()


@transforms.add
def add_build_config(config, tasks):
    for task in tasks:
        params = config.params
        head_rev = params["head_rev"]
        channel = params.get("channel", "dev")
        head_ref = params["head_ref"]
        if head_ref.startswith("refs/heads/"):
            head_ref = head_ref[len("refs/heads/") :]

        task.setdefault("worker", {})
        task["worker"]["command"] = [
            "taskboot",
            "build",
            "--image",
            "mozilla/code-coverage",
            "--tag",
            f"bot-{channel}",
            "--tag",
            f"bot-{head_rev}",
            "--write",
            "/bot.tar",
            "bot/Dockerfile",
        ]
        task["worker"].setdefault("env", {}).update(
            {
                "GIT_REPOSITORY": params["head_repository"],
                "GIT_REVISION": head_rev,
            }
        )

        if params["tasks_for"] == "github-pull-request":
            prefix = "code-coverage-pr"
        else:
            prefix = "code-coverage"
        task.setdefault("routes", []).extend(
            [
                f"index.code-analysis.v2.{prefix}.revision.{head_rev}",
                f"index.code-analysis.v2.{prefix}.branch.{head_ref}",
            ]
        )

        yield task
