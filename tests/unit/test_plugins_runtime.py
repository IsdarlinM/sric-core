import json
import pytest
from sric.plugins import PluginPermission, PluginRegistry


def test_plugin_lifecycle_and_permissions(tmp_path):
    src = tmp_path / 'm.json'
    src.write_text(json.dumps({"name": "demo", "version": "1.0", "api_version": "1", "type": "collector", "permissions": ["filesystem_read"], "capabilities": ["demo"], "entrypoint": "demo:Plugin"}))
    reg = PluginRegistry(tmp_path / 'plugins')
    m = reg.install_manifest(src)
    reg.assert_permission(m, PluginPermission.FILESYSTEM_READ)
    reg.disable('demo')
    with pytest.raises(PermissionError): reg.assert_permission(m, PluginPermission.FILESYSTEM_READ)
    assert reg.verify('demo')['valid'] is True
    reg.enable('demo')
    reg.remove('demo')
    with pytest.raises(KeyError): reg.inspect('demo')
