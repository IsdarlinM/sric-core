from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _sha256(value: bytes) -> bytes:
    return hashlib.sha256(value).digest()


def hash_leaf(value: bytes) -> bytes:
    return _sha256(b"\x00" + value)


def hash_node(left: bytes, right: bytes) -> bytes:
    return _sha256(b"\x01" + left + right)


class ProofSide(StrEnum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class MerkleProofStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sibling_sha256: str
    side: ProofSide

    @field_validator("sibling_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if len(value) != 64:
            raise ValueError("sibling_sha256 must be a 64-character SHA-256 hex digest")
        try:
            bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError("sibling_sha256 must be hexadecimal") from exc
        return value.lower()


class MerkleProof(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tree_size: int = Field(ge=1)
    leaf_index: int = Field(ge=0)
    leaf_sha256: str
    root_sha256: str
    steps: list[MerkleProofStep] = Field(default_factory=list)

    @field_validator("leaf_sha256", "root_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        if len(value) != 64:
            raise ValueError("Merkle hashes must be 64-character SHA-256 hex digests")
        try:
            bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError("Merkle hashes must be hexadecimal") from exc
        return value.lower()


class EvidenceDigest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    content_sha256: str

    @field_validator("content_sha256")
    @classmethod
    def validate_content_hash(cls, value: str) -> str:
        if len(value) != 64:
            raise ValueError("content_sha256 must be a 64-character SHA-256 hex digest")
        try:
            bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError("content_sha256 must be hexadecimal") from exc
        return value.lower()

    def canonical_bytes(self) -> bytes:
        return self.evidence_id.encode("utf-8") + b"\x00" + bytes.fromhex(self.content_sha256)


def merkle_root(leaves: Sequence[bytes]) -> str:
    if not leaves:
        raise ValueError("at least one leaf is required")
    level = [hash_leaf(value) for value in leaves]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            hash_node(level[index], level[index + 1])
            for index in range(0, len(level), 2)
        ]
    return level[0].hex()


def build_merkle_proof(leaves: Sequence[bytes], leaf_index: int) -> MerkleProof:
    if not leaves:
        raise ValueError("at least one leaf is required")
    if leaf_index < 0 or leaf_index >= len(leaves):
        raise IndexError("leaf_index is outside the tree")

    original_size = len(leaves)
    index = leaf_index
    level = [hash_leaf(value) for value in leaves]
    steps: list[MerkleProofStep] = []
    leaf_hash = level[index]

    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        if index % 2:
            sibling_index = index - 1
            side = ProofSide.LEFT
        else:
            sibling_index = index + 1
            side = ProofSide.RIGHT
        steps.append(
            MerkleProofStep(
                sibling_sha256=level[sibling_index].hex(),
                side=side,
            )
        )
        level = [
            hash_node(level[position], level[position + 1])
            for position in range(0, len(level), 2)
        ]
        index //= 2

    return MerkleProof(
        tree_size=original_size,
        leaf_index=leaf_index,
        leaf_sha256=leaf_hash.hex(),
        root_sha256=level[0].hex(),
        steps=steps,
    )


def verify_merkle_proof(value: bytes, proof: MerkleProof) -> bool:
    if proof.leaf_index >= proof.tree_size:
        return False
    current = hash_leaf(value)
    if current.hex() != proof.leaf_sha256:
        return False
    for step in proof.steps:
        sibling = bytes.fromhex(step.sibling_sha256)
        if step.side is ProofSide.LEFT:
            current = hash_node(sibling, current)
        else:
            current = hash_node(current, sibling)
    return current.hex() == proof.root_sha256


def evidence_merkle_root(evidence: Sequence[EvidenceDigest]) -> str:
    if len({item.evidence_id for item in evidence}) != len(evidence):
        raise ValueError("evidence_id values must be unique")
    ordered = sorted(evidence, key=lambda item: item.evidence_id)
    return merkle_root([item.canonical_bytes() for item in ordered])
