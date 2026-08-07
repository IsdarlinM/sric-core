# SDK compatibility and graph interchange

SRIC 0.4.1 exposes a provider-neutral public compatibility contract through `SDKManifest`.

A manifest declares:

- SDK version and supported SRIC core window;
- required plugin types and permissions;
- accepted schema versions;
- deprecated features and migration notes.

`check_sdk_compatibility` fails closed when the core version, permissions, plugin types or schemas do not match. Compatibility never grants permissions and never enables a plugin automatically.

## Graph interchange

`export_jsonld` and `export_graphml` provide deterministic evidence-bearing graph exports. Node and edge status, evidence and counter-evidence are retained. Exports reject edges that reference nodes absent from the export set.

JSON-LD and GraphML are interchange formats, not validation formats. Exporting an `INFERRED` relationship never upgrades it to `OBSERVED` or `VALIDATED`.

Loopback API endpoints:

```text
POST /api/v1/evidence-native/sdk/compatibility
POST /api/v1/evidence-native/graph/export
```
