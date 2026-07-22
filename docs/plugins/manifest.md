# Plugin Manifest

Plugins declare type, API version, entrypoint, capabilities, and permissions (`network`, `filesystem_read`, `filesystem_write`, `secrets`, `ai`, `active_requests`). Declared permission is necessary but never sufficient: active operations must still pass Scope and Policy engines.
