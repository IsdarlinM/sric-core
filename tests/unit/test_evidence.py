from pathlib import Path
from sric.evidence import EvidenceStore
from sric.models import Provenance, ProvenanceType


def test_evidence_is_content_addressed_and_verified(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    p = Provenance(provenance_type=ProvenanceType.USER_INPUT, source="test", method="fixture")
    ref = store.put_bytes(b"hello", media_type="text/plain", provenance=p)
    assert store.get_bytes(ref) == b"hello"
    assert len(ref.sha256) == 64
