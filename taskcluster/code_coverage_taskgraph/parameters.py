from voluptuous import Optional

from taskgraph.parameters import extend_parameters_schema


extend_parameters_schema(
    {
        Optional("channel"): str,
    },
)


def decision_parameters(graph_config, parameters):
    head_ref = parameters["head_ref"]
    if head_ref.startswith("refs/heads/"):
        head_ref = head_ref[len("refs/heads/"):]

    if head_ref == "production":
        parameters["channel"] = "production"
    elif head_ref == "testing":
        parameters["channel"] = "testing"
    else:
        parameters["channel"] = "dev"
