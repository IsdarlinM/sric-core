# Signed release manifests

Production updates must not use blind `git pull`. Release wheels are hashed with SHA-256 and the update manifest is signed with an offline Ed25519 release key. The private key is never committed or uploaded as a normal repository artifact.

Example:

```bash
python scripts/release-manifest.py \
  --product sric-core \
  --version X.Y.Z \
  --wheel dist/package-X.Y.Z-py3-none-any.whl \
  --artifact-url https://RELEASE-HOST/package-X.Y.Z-py3-none-any.whl \
  --private-key /secure/offline/release-key.pem \
  --output dist/release-manifest.json
```

Publish the corresponding public Ed25519 trust root through a separately authenticated channel. Before stable releases, test clean install, upgrade from the prior supported release, backup/migration behavior, signature failure, checksum failure, and rollback behavior.
