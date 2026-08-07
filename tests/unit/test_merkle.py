import hashlib

import pytest

from sric.merkle import (
    EvidenceDigest,
    build_merkle_proof,
    evidence_merkle_root,
    merkle_root,
    verify_merkle_proof,
)


def test_merkle_proofs_verify_for_even_and_odd_trees() -> None:
    for leaves in ([b"one", b"two"], [b"one", b"two", b"three"]):
        root = merkle_root(leaves)
        for index, value in enumerate(leaves):
            proof = build_merkle_proof(leaves, index)
            assert proof.root_sha256 == root
            assert verify_merkle_proof(value, proof) is True


def test_modified_leaf_does_not_verify() -> None:
    proof = build_merkle_proof([b"one", b"two", b"three"], 1)

    assert verify_merkle_proof(b"modified", proof) is False


def test_evidence_root_is_deterministic_by_evidence_id() -> None:
    first = EvidenceDigest(
        evidence_id="E-1", content_sha256=hashlib.sha256(b"one").hexdigest()
    )
    second = EvidenceDigest(
        evidence_id="E-2", content_sha256=hashlib.sha256(b"two").hexdigest()
    )

    assert evidence_merkle_root([first, second]) == evidence_merkle_root([second, first])


def test_duplicate_evidence_ids_are_rejected() -> None:
    value = EvidenceDigest(
        evidence_id="E-1", content_sha256=hashlib.sha256(b"one").hexdigest()
    )

    with pytest.raises(ValueError, match="must be unique"):
        evidence_merkle_root([value, value])


def test_empty_tree_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one leaf"):
        merkle_root([])


def test_out_of_range_proof_index_is_rejected() -> None:
    with pytest.raises(IndexError, match="outside the tree"):
        build_merkle_proof([b"one"], 1)
