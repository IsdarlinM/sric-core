# Threat Model v0.2

## Assets
Evidence, secrets, scope rules, workspaces, plugin permissions, AI prompts, reports and update metadata.

## Primary threats and current controls
- Prompt injection: external content is represented only as untrusted payload; AI cannot alter Scope/Policy engines.
- SSRF: scope evaluation supports resolved-IP checks and blocks private/special networks unless explicitly allowed.
- Cross-workspace leakage: each workspace has separate DB/evidence directories.
- Secret leakage: default redaction for Authorization/Cookie/API-key-like material before audit use.
- Plugin compromise: declarative permissions; no plugin auto-execution in v0.2.
- Unauthorized Web API: non-loopback binding remains denied until authenticated TLS mode is implemented.
- Supply-chain update tampering: signed canonical release manifest + SHA-256 artifact verification; insecure HTTP rejected.
- Active-request abuse: shared global/per-host rate limiter; consumers must keep it in the executor gate path.
- Poisoned imports/archives: delegated to consuming importers; they must enforce size/path/schema limits.
