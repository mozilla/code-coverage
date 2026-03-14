from voluptuous import Optional

from taskgraph.parameters import extend_parameters_schema
from taskgraph.target_tasks import register_target_task


extend_parameters_schema(
    {
        Optional("channel"): str,
    },
)


@register_target_task("default")
def target_tasks_default(full_task_graph, parameters, graph_config):
    return [
        label
        for label, task in full_task_graph.tasks.items()
        if parameters["tasks_for"]
        in task.attributes.get("run-on-tasks-for", [parameters["tasks_for"]])
    ]


def decision_parameters(graph_config, parameters):
    head_ref = parameters["head_ref"]
    if head_ref.startswith("refs/heads/"):
        head_ref = head_ref[len("refs/heads/") :]

    if head_ref == "production":
        parameters["channel"] = "production"
    elif head_ref == "testing":
        parameters["channel"] = "testing"
    else:
        parameters["channel"] = "dev"
