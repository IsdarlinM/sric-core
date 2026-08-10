from __future__ import annotations

from sric.web_console import build_command_catalog
from sric.web_workbench import assert_feature_contract, build_feature_catalog


def test_every_cli_command_and_parameter_has_structured_web_representation() -> None:
    cli = {item["path"]: item for item in build_command_catalog("sric.cli_all")}
    web = {item["path"]: item for item in build_feature_catalog("sric.cli_all")}

    contract = assert_feature_contract("sric.cli_all")
    assert contract["complete"] is True
    assert set(cli) == set(web)

    allowed_controls = {
        "text",
        "path",
        "number",
        "flag",
        "tri-state",
        "count",
        "multi-text",
        "multi-value",
        "select",
        "multi-select",
    }
    for path, command in cli.items():
        assert [item["name"] for item in command["params"]] == [
            item["name"] for item in web[path]["params"]
        ]
        assert web[path]["category"]
        assert web[path]["classification"] == command["classification"]
        assert web[path]["approval_required"] == command["approval_required"]
        assert web[path]["context_only"] == command["context_only"]
        for param in web[path]["params"]:
            assert param["control"] in allowed_controls
            assert param["id"]


def test_web_command_is_context_only_but_still_visible_as_feature() -> None:
    features = {item["path"]: item for item in build_feature_catalog("sric.cli_all")}
    assert features["web"]["context_only"] is True
    assert features["web"]["executable"] is False
    assert features["web"]["web_surface"] == "context"


def test_sensitive_cli_options_never_render_as_plain_text_controls() -> None:
    features = build_feature_catalog("sric.cli_all")
    for feature in features:
        for param in feature["params"]:
            if any(
                marker in param["name"].lower()
                for marker in ("token", "secret", "password", "cookie", "api_key", "private_key")
            ):
                assert param["sensitive"] is True


def test_choice_parameters_are_exposed_as_select_controls() -> None:
    features = build_feature_catalog("sric.cli_all")
    for feature in features:
        for param in feature["params"]:
            if param.get("choices"):
                assert param["control"] in {"select", "multi-select"}
