# Sentinel Forge local release train

Sentinel Forge does not require GitHub Actions or another hosted CI service. Place the six repositories as siblings:

```text
workspace/
  sric-core/
  reprosec/
  authtwin/
  fossilscope/
  trustboundary/
  exposuredna/
```

Install each repository's development dependencies, then run from `sric-core`:

```bash
python scripts/release-ecosystem.py --root ..
```

The command runs each repository's `scripts/release-gate.py` in dependency order, validates SRIC/ReproSec version constraints and writes the combined report to:

```text
sric-core/build/release-evidence/ecosystem-release-gate.json
```

A fast developer pass is available with `--quick`; it is not release evidence. `--only REPOSITORY` can restrict execution while still checking the complete compatibility matrix. `--offline` forwards offline wheel behavior to repository gates.

The ecosystem release status is `PASS` only when every selected repository gate and every compatibility check pass. Do not tag or publish an ecosystem release from a `FAIL` report.
