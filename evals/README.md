# Versioned AI / agentic evals

These evals use synthetic data and a deterministic local fixture provider. They verify invariants around prompt-injection labeling, proposal truth state and executor separation; they do **not** claim model accuracy.

Run:

```bash
PYTHONPATH=src python scripts/run-evals.py
```

Any future prompt/model/provider change must add or update versioned datasets and expected outcomes. External target content remains untrusted data regardless of model behavior.
