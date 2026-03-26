from taskgraph.transforms.base import TransformSequence

transforms = TransformSequence()


@transforms.add
def add_index_routes(config, tasks):
    for task in tasks:
        params = config.params
        head_rev = params["head_rev"]
        head_ref = params["short_head_ref"]

        if params["tasks_for"] == "github-pull-request":
            index_prefix = "code-coverage-pr"
        else:
            index_prefix = "code-coverage"

        trust_domain = config.graph_config["trust-domain"]
        task.setdefault("routes", []).extend(
            [
                f"index.{trust_domain}.v2.{index_prefix}.revision.{head_rev}",
                f"index.{trust_domain}.v2.{index_prefix}.branch.{head_ref}",
            ]
        )

        yield task
