import yaml
from schema import Optional, Regex, Schema

__all__ = ["load"]

sequence_schema: dict = Schema({
    Optional("version"): Regex(r"\d+\.\d+"),
    "name": str,
    Optional("description"): str,
    "measurements": [
        {
            "type": str,
            "name": str,
            Optional("enabled"): bool,
            Optional("description"): str,
            Optional("namespace"): str,
            Optional("strips"): str,
            Optional("parameters"): {
                str: object
            },
            Optional("strip_measurements"): [{
                "type": str,
                "name": str,
                Optional("enabled"): bool,
                Optional("description"): str,
                Optional("interval"): int,
                Optional("parameters"): {
                    str: object
                }
            }]
        }
    ]
})


def validate(sequence):
    return sequence_schema.validate(sequence)


def load(fp):
    sequence = yaml.safe_load(fp)
    return validate(sequence)
