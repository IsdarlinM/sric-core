#!/usr/bin/env python3
"""Create a signed update manifest for one wheel without storing private keys in the repo."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--artifact-url", required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    wheel = args.wheel.resolve(strict=True)
    if wheel.suffix != ".whl":
        raise SystemExit("release artifact must be a .whl")
    key = serialization.load_pem_private_key(args.private_key.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit("private key must be Ed25519")
    unsigned = {
        "product": args.product,
        "version": args.version,
        "artifact": args.artifact_url,
        "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
    }
    payload = (json.dumps(unsigned, sort_keys=True, separators=(",", ":")) + "\n").encode()
    manifest = dict(unsigned)
    manifest["signature"] = base64.b64encode(key.sign(payload)).decode("ascii")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
