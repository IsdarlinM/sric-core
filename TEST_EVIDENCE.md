# Test Evidence — SRIC Core v0.5.12 Candidate

## Candidate review — 2026-08-10

The `audit/exception-boundary-0512` candidate adds shared operational-failure hardening used by all Sentinel Forge products:

- bounded redacted operational exception messages;
- default CLI traceback containment with explicit `SENTINEL_DEBUG=1` developer opt-in;
- Web Command Console runner exception containment;
- structured redacted HTTP 503 catalog failures;
- bounded terminate/kill/wait handling with background child reaping;
- bounded retained terminal-job tombstones for concurrent SSE/status readers;
- persisted Job Engine error/event/metadata/provenance redaction;
- expanded audit and recursive structured redaction;
- runtime compatibility and troubleshooting documentation updates.

## Focused execution performed

A local focused behavioral harness was constructed around the newly changed Web Console and Job Engine runtime paths because the authenticated GitHub connector cannot materialize a complete repository checkout in the execution container.

The first focused run reported:

```text
3 passed, 1 failed
```

The failure exposed a real race: the background process reaper could record the final child return code and then the synchronous timeout path could overwrite it with `None`. The implementation was corrected so an unreaped synchronous path never overwrites a return code recorded by the background reaper.

The focused harness was then rerun:

```text
4 passed in 0.19s
```

Covered behaviors:

1. unexpected command-catalog construction failure returns a structured HTTP 503 and redacts password/token material;
2. terminal-job pruning retains a bounded tombstone readable by concurrent snapshot/SSE consumers;
3. a child process that remains alive through the final synchronous post-kill wait is contained and background-reaped without blocking indefinitely;
4. Job Engine failure text and sensitive operational metadata are redacted before persistence.

This is **focused regression evidence only**. It is not represented as full repository, platform or ecosystem release evidence.

## Hosted CI status for the candidate

**THE COMPLETE v0.5.12 TEST/RELEASE GATES HAVE NOT EXECUTED.**

GitHub Actions creates the Linux/Windows, Python 3.11/3.12/3.13, installer-smoke and release-gate jobs, but they have `runner_id=0`, `steps=[]` and never allocate a runner. GitHub reports:

```text
The job was not started because your account is locked due to a billing issue.
```

A workflow that executes zero steps is infrastructure failure, not test evidence. No pytest, static-analysis, installer, build, browser-E2E, supply-chain or ecosystem PASS is claimed from those hosted runs.

## Required exact-commit evidence before release completion

From a directory containing the six candidate checkouts:

```bash
python -m sric.standalone_gate --root sric-core
python sric-core/scripts/release-standalone-ecosystem.py --root .
python sric-core/scripts/release-gate.py
python sric-core/scripts/release-ecosystem.py --root .
```

Release completion additionally requires:

- full unit, integration, E2E, security and fuzz suites;
- AI evals;
- CLI help execution for every public command and all supported help aliases;
- exact CLI/Web command and parameter parity;
- Web Console and Workbench page/assets/browser interaction checks;
- GET/POST/SSE API contract tests, mutation approval and CSRF controls;
- clean Linux/Termux and Windows installation;
- repair and signed-update/rollback checks preserving configuration/workspaces/evidence;
- dependency, secret, SAST and SBOM/release supply-chain checks;
- platform/browser evidence tied to the exact final source commit/tree.

Until those exact-commit gates execute successfully, the candidate must not be described as a completed release even though the focused runtime regressions above pass.