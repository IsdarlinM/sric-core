# ADR-0001: Local-first modular core

Status: Accepted

SRIC starts as a Python package plus local API rather than microservices. This minimizes operational attack surface, supports offline use, and keeps schema/policy behavior testable. PostgreSQL and distributed collaboration remain future adapters, not MVP requirements.
