"""Offline structural checks, not a claim of AWS deployment validation."""

import json
from pathlib import Path
import yaml


class Loader(yaml.SafeLoader):
    pass


Loader.add_multi_constructor(
    "!",
    lambda loader, tag, node: {"Fn::" + tag: loader.construct_scalar(node)}
    if isinstance(node, yaml.ScalarNode)
    else {"Fn::" + tag: loader.construct_sequence(node)},
)

root = Path(__file__).resolve().parents[1]
for p in (root / "infrastructure").rglob("*.json"):
    json.loads(p.read_text())
for p in [root / "template.yaml", *root.glob("backend/lambda/*/template.yaml")]:
    data = yaml.load(p.read_text(), Loader=Loader)
    for resource in data["Resources"].values():
        props = resource.get("Properties", {})
        if "CodeUri" in props:
            assert (p.parent / props["CodeUri"] / "lambda_function.py").is_file(), p
        if "ContentUri" in props:
            assert (
                p.parent / props["ContentUri"] / "python/spill_common.py"
            ).is_file(), p
main = yaml.load((root / "template.yaml").read_text(), Loader=Loader)
assert main["Resources"]["Api"]["Properties"]["Auth"]["DefaultAuthorizer"] == "AWS_IAM"
for legacy in ["SensorDataProcessor", "SpillEmailNotifier"]:
    assert legacy not in main["Resources"]
print("JSON parse, SAM code/layer paths and API security assertions: PASS")
