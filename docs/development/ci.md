# CI and private SRIC dependency

All workflows run with `contents: read`, pinned GitHub Action commit SHAs, `persist-credentials: false`, tests, static checks, a local high-confidence security scan, SBOM generation, package build, Bandit SAST and pip-audit dependency scanning.

For repositories that depend on the private `sric-core` repository, configure a repository secret named `SRIC_READ_TOKEN` containing a fine-grained GitHub token with **read-only Contents access to `sric-core` only**. Do not grant write, Actions, administration, or organization-wide permissions. Rotate the token and prefer an organization/repository-scoped GitHub App when the repositories become public or organizational governance is introduced.

CI never receives production secrets, target credentials, capsules, or workspace data.
