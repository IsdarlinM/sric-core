# Test Evidence — sric-core v0.4.0

Validated on 2026-07-22 as part of the Sentinel Forge vNext release gate.

- pytest: **57 tests passed**
- Python compileall: **PASS**
- project security scan: **PASS**
- CLI registered-command help coverage: **PASS** (`--help`, `-h`; 43 registered SRIC command paths)
- synthetic/local functional smoke: **PASS**
- YAML parse validation: **PASS** as part of the 42-file ecosystem gate
- wheel build: **PASS**
- isolated wheel smoke against the validated runtime dependency layer: **PASS**

Ecosystem-wide validated totals after CLI modularization: **208 tests passed** across six repositories and **263 registered CLI command paths** passed `--help`/`-h` coverage.

## Explicit environment limitations

- Fresh dependency-resolving installation was blocked by the environment package index lacking required current packages such as `fastapi>=0.128`; wheel construction passed.
- Ruff, mypy and pip-audit were unavailable from the local runtime/index for a fresh rerun; CI remains configured to run them where dependencies are available.
- Windows `.cmd` installers were not executable in this Linux runtime; Linux shell installer syntax was validated with `sh -n`.
- Real-browser E2E is not claimed from this runtime; API/Web/CSP/MIME integration tests are covered by automated suites.
