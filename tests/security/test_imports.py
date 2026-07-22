import zipfile
import pytest
from sric.imports import SafeImportPipeline


def test_rejects_zip_traversal(tmp_path):
    p = tmp_path / "bad.zip"
    with zipfile.ZipFile(p, "w") as z: z.writestr("../escape.txt", "x")
    with pytest.raises(ValueError): SafeImportPipeline().inspect_zip(p)
