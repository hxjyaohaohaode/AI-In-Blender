import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile
from tools.build import build


class PackagingTests(unittest.TestCase):
    def test_installable_layouts_and_reproducible_archives(self):
        with tempfile.TemporaryDirectory() as folder:
            outputs = build(folder)
            hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in outputs]
            for path in outputs:
                with zipfile.ZipFile(path) as archive:
                    names = archive.namelist()
                    self.assertTrue(all(info.create_system == 3 for info in archive.infolist()))
                    self.assertFalse(
                        any("__pycache__" in n or ".env" in n or "tests/" in n for n in names)
                    )
                    prefix = "ai_modeling_assistant/" if "legacy" in path.name else ""
                    self.assertIn(prefix + "__init__.py", names)
                    self.assertIn(prefix + "worker.py", names)
                    self.assertEqual("blender_manifest.toml" in names, "extension" in path.name)
            self.assertEqual(
                hashes, [hashlib.sha256(p.read_bytes()).hexdigest() for p in build(folder)]
            )
            self.assertTrue((Path(folder) / "SHA256SUMS.txt").is_file())
            self.assertNotIn(b"\r", (Path(folder) / "SHA256SUMS.txt").read_bytes())
