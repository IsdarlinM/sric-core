import json
from sric.models import ActionClass, ActionProposal, OperationMode
from sric.plugin_sdk import PluginBroker, PluginResult
from sric.plugins import PluginPermission, PluginRegistry


class DemoPlugin:
    def run(self, context, payload):
        return PluginResult(
            observations=[{"value": payload["value"], "mode": context.mode}],
            proposed_actions=[ActionProposal(action_id="A1", actor="plugin:demo", method="GET", action_class=ActionClass.READ_ONLY_SAFE, target="https://example.test", mode=OperationMode.PASSIVE)],
        )


def test_plugin_broker_returns_proposals_not_executor(tmp_path):
    registry = PluginRegistry(tmp_path / "plugins")
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps({
        "name":"demo","version":"1.0","api_version":"1","type":"analyzer",
        "permissions":["filesystem_read"],"capabilities":["demo"],"entrypoint":"demo:Plugin"
    }))
    manifest = registry.install_manifest(manifest_file)
    result = PluginBroker(registry).invoke_trusted(
        manifest, DemoPlugin(), workspace=tmp_path, payload={"value":"x"},
        required_permissions={PluginPermission.FILESYSTEM_READ},
    )
    assert result.observations[0]["value"] == "x"
    assert result.proposed_actions[0].target == "https://example.test"


def test_plugin_permission_fails_closed(tmp_path):
    registry = PluginRegistry(tmp_path / "plugins")
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps({
        "name":"demo","version":"1.0","api_version":"1","type":"analyzer",
        "permissions":[],"capabilities":[],"entrypoint":"demo:Plugin"
    }))
    manifest = registry.install_manifest(manifest_file)
    try:
        PluginBroker(registry).invoke_trusted(
            manifest, DemoPlugin(), workspace=tmp_path, payload={"value":"x"},
            required_permissions={PluginPermission.NETWORK},
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("undeclared permission must fail closed")
