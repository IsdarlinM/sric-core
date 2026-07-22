# Signed updates

`SRIC_RELEASE_MANIFEST_URL` and `SRIC_RELEASE_PUBLIC_KEY` may configure the release channel, or pass `--manifest` and `--public-key` explicitly.

```bash
sric update --check --manifest release.json --public-key release.pub.pem
```

The manifest is Ed25519-signed over canonical JSON and contains the release wheel SHA-256. HTTP sources are rejected. The updater accepts signed wheels only and invokes pip without dependency expansion. A default trust root is intentionally not embedded before the official release signing process exists.
