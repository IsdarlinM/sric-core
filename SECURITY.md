# Security Policy

Use SRIC only on systems you own or are explicitly authorized to assess.

## Reporting a vulnerability
Do not open a public issue for an exploitable vulnerability. Use the repository's private security advisory channel when the repository is published. Include affected version, reproduction, impact, and minimal evidence.

## Supported versions
During pre-1.0 development, only the latest release receives security fixes unless otherwise stated.

## Security invariants
- Untrusted imported/target content is data, never policy or instructions.
- Plugins cannot bypass Scope/Policy decisions by design contract.
- Secrets must not appear in audit/debug logs.
- AI output cannot directly produce a `VALIDATED` security finding without deterministic evidence.
