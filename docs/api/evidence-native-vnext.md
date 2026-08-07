# Evidence-native analysis API

Run the extended SRIC local API on loopback:

```bash
python -m uvicorn sric.api_vnext:create_app --factory --host 127.0.0.1 --port 8764
```

Additional endpoints:

```text
POST /api/v1/evidence-native/confidence/analyze
POST /api/v1/evidence-native/confidence/calibration
POST /api/v1/evidence-native/bitemporal/query
POST /api/v1/evidence-native/sources/independence
POST /api/v1/evidence-native/integrity/merkle
```

Confidence analysis always includes a Skeptic result and never creates a validated finding. Bitemporal queries keep valid time separate from knowledge time. Source analysis distinguishes raw sources from independent upstream groups. Merkle roots and proofs provide tamper-evident set membership, not truthfulness or completeness.
