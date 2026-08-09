# Signed updates

`SRIC_RELEASE_MANIFEST_URL` and `SRIC_RELEASE_PUBLIC_KEY` may configure the release channel, or pass `--manifest` and `--public-key` explicitly.

```bash
sric update --check --manifest release.json --public-key release.pub.pem
sric update --manifest release.json --public-key release.pub.pem
sric update --force --manifest release.json --public-key release.pub.pem
```

`--force` is an explicit reinstall mode. When the signed manifest selects the same version that is already installed, SRIC downloads and verifies that release wheel and invokes pip with `--force-reinstall`. It may also install a newer signed release, but it never permits a downgrade. `--check` and `--force` are mutually exclusive.

The manifest is Ed25519-signed over canonical JSON and contains the release wheel SHA-256. HTTP sources are rejected. The updater accepts signed wheels only and invokes pip without dependency expansion. State is backed up before installation. Normal upgrades require a verified rollback wheel; a same-version forced reinstall uses the verified same-version release wheel as its package recovery artifact.

A default trust root is intentionally not embedded before the official release signing process exists. Until a signed release channel and trusted public key are published, `sric update` requires explicit release-channel configuration rather than falling back to `git pull` or an unsigned download.
