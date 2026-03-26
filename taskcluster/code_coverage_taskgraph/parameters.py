from typing import Optional

from taskgraph.parameters import extend_parameters_schema
from taskgraph.util.schema import Schema

extend_parameters_schema(
    Schema.from_dict(
        {
            "channel": Optional[str],
            "short_head_ref": Optional[str],
        },
        name="CodeCoverageParametersSchema",
    ),
)


def decision_parameters(graph_config, parameters):
    short_head_ref = parameters["head_ref"]
    for prefix in ("refs/heads/", "refs/tags/"):
        if short_head_ref.startswith(prefix):
            short_head_ref = short_head_ref[len(prefix) :]
            break
    parameters["short_head_ref"] = short_head_ref

    if short_head_ref == "testing":
        parameters["channel"] = "testing"
    elif short_head_ref == "production":
        parameters["channel"] = "production"
    else:
        parameters["channel"] = "dev"
