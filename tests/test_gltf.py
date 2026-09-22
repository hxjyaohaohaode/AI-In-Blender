import json
from pathlib import Path
import struct
import tempfile
import unittest
from ai_modeling_assistant.core.gltf import inspect_glb


class ExportValidationTests(unittest.TestCase):
    def check(self, data, *, binary=b"\0" * 36, trailing=b""):
        encoded = json.dumps(data).encode()
        encoded += b" " * (-len(encoded) % 4)
        raw = struct.pack("<4sII", b"glTF", 2, 28 + len(encoded) + len(binary))
        raw += struct.pack("<I4s", len(encoded), b"JSON") + encoded
        raw += struct.pack("<I4s", len(binary), b"BIN\0") + binary + trailing
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "asset.glb"
            path.write_bytes(raw)
            return inspect_glb(path)

    def document(self):
        return {
            "asset": {"version": "2.0"},
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
            "accessors": [{"count": 3, "type": "VEC3", "componentType": 5126, "bufferView": 0}],
            "buffers": [{"byteLength": 36}],
            "bufferViews": [{"buffer": 0, "byteLength": 36}],
        }

    def test_valid_self_contained_asset(self):
        self.assertEqual(self.check(self.document())["vertices"], 3)

    def test_empty_unreachable_and_malformed_geometry_are_rejected(self):
        for key, value in (("nodes", []), ("meshes", []), ("scenes", []), ("accessors", [])):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check(dict(self.document(), **{key: value}))

    def test_external_images_and_out_of_bounds_buffers_are_rejected(self):
        for fields in (
            {"images": [{"uri": "lost.png"}]},
            {"bufferViews": [{"buffer": 0, "byteLength": 100}]},
            {"buffers": [{"uri": "lost.bin", "byteLength": 36}]},
        ):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.check(dict(self.document(), **fields))

    def test_truncated_or_appended_data_does_not_pass(self):
        with self.assertRaisesRegex(ValueError, "declared length"):
            self.check(self.document(), trailing=b"extra")

    def test_accessor_cannot_claim_vertices_outside_binary_data(self):
        document = self.document()
        document["accessors"][0]["count"] = 1000
        with self.assertRaisesRegex(ValueError, "accessor exceeds"):
            self.check(document)


if __name__ == "__main__":
    unittest.main()
