"""Loopback protocol fixtures. Never contacts external model services."""

import base64
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import io
import json
import hashlib
from pathlib import Path
import struct
import time
import wave
import zlib


def png_bytes():
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress((b"\x00" + b"\x00\x80\xff" * 2) * 2))
        + chunk(b"IEND", b"")
    )


PNG = png_bytes()


def triangle_glb():
    binary = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    document = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "FixtureTriangle"}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [{"buffer": 0, "byteLength": len(binary), "target": 34962}],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
                "min": [0, 0, 0],
                "max": [1, 1, 0],
            }
        ],
    }
    raw = json.dumps(document).encode()
    raw += b" " * (-len(raw) % 4)
    return (
        b"glTF"
        + struct.pack("<II", 2, 12 + 8 + len(raw) + 8 + len(binary))
        + struct.pack("<I", len(raw))
        + b"JSON"
        + raw
        + struct.pack("<I", len(binary))
        + b"BIN\x00"
        + binary
    )


def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, "wb") as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(8000)
        sound.writeframes(b"\x00\x00" * 2000)
    return output.getvalue()


class Handler(BaseHTTPRequestHandler):
    job_posts = 0

    def log_message(self, *args):
        pass

    def send(self, value, status=200, content_type="application/json"):
        raw = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.path.endswith("/audio/transcriptions"):
            assert b'name="file"' in raw and b'name="model"' in raw
            return self.send({"text": "Rotate the object slowly"})
        data = json.loads(raw)
        if self.path.endswith("/chat/completions"):
            if data["model"] == "error":
                return self.send({"error": "sensitive-token"}, 503)
            if data["model"] == "slow":
                time.sleep(10)
            assert all("content" in m for m in data["messages"])
            system = (
                data["messages"][0]["content"] if data["messages"][0]["role"] == "system" else ""
            )
            prompt = data["messages"][-1]["content"]
            if isinstance(prompt, list):
                for part in prompt:
                    if part.get("type") == "image_url":
                        assert base64.b64decode(
                            part["image_url"]["url"].split(",", 1)[1]
                        ).startswith(b"\x89PNG")
            prompt_text = (
                "\n".join(p.get("text", "") for p in prompt if p.get("type") == "text")
                if isinstance(prompt, list)
                else prompt
            )
            current_request = "\n".join(prompt_text.splitlines()[:2])
            if "persistent Blender production collaborator" in system:
                content = (
                    "Dialogue reply; received "
                    + str(len(data["messages"]))
                    + " messages. Keep the blue material and requested dimensions."
                )
            elif "Propose useful memories" in system:
                content = '{"memories":[]}'
            elif "Compress a Blender production conversation" in system:
                source = json.loads(prompt)
                content = json.dumps(
                    {
                        "goals": [
                            {
                                "text": "Retain project dimensions and blue style",
                                "sources": source["source_ids"][:1],
                            }
                        ]
                    }
                )
            elif "production planner" in system:
                content = json.dumps(
                    {
                        "tasks": [
                            {"id": "mesh", "expert": "modeler", "prompt": "Create one cube"},
                            {
                                "id": "material",
                                "expert": "material",
                                "prompt": "Give it a blue material",
                                "depends_on": ["mesh"],
                            },
                            {
                                "id": "check",
                                "expert": "inspector",
                                "prompt": "Inspect",
                                "depends_on": ["material"],
                            },
                            {
                                "id": "review",
                                "expert": "reviewer",
                                "prompt": "Review",
                                "depends_on": ["check"],
                            },
                            {
                                "id": "export",
                                "expert": "exporter",
                                "prompt": "Export",
                                "depends_on": ["review"],
                            },
                        ]
                    }
                )
            elif "passed (boolean)" in system:
                content = json.dumps(
                    {
                        "passed": "REJECT_REVIEW" not in current_request,
                        "summary": "Fixture review",
                        "issues": [],
                    }
                )
            elif "Create PBR materials" in system:
                content = "import bpy\nmat=bpy.data.materials.new('FixtureBlue')\nmat.diffuse_color=(0.02,0.3,0.8,1)\nfor obj in bpy.context.selected_objects:\n    if obj.type=='MESH': obj.data.materials.append(mat)"
            elif "Creative review needs changes:" in prompt_text:
                # Review-failure fixtures deliberately cannot be fixed. Preserve
                # existing geometry while exercising bounded repair + re-review.
                content = "pass"
            elif "FAIL_ONCE" in current_request and "last code failed" not in prompt_text:
                content = "import bpy\nbpy.ops.mesh.primitive_cube_add()\nbpy.context.object.name='Partial'\nraise ValueError('Intentional fixture failure')"
            else:
                content = "import bpy\nbpy.ops.mesh.primitive_cube_add(size=1)\nbpy.context.object.name='FixtureCube'"
            return self.send(
                {
                    "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 11, "completion_tokens": 17},
                }
            )
        if self.path.endswith("/images/generations"):
            return self.send({"data": [{"b64_json": base64.b64encode(PNG).decode()}]})
        if self.path.endswith("/audio/speech"):
            return self.send(wav_bytes(), content_type="audio/wav")
        if self.path.endswith("/text-to-3d"):
            return self.send({"result": "refined" if data.get("mode") == "refine" else "preview"})
        if self.path.endswith("/assets"):
            binary = base64.b64decode(data["data_base64"])
            assert hashlib.sha256(binary).hexdigest() == data["sha256"]
            return self.send({"id": "uploaded-" + data["sha256"][:12]})
        if self.path.endswith("/jobs"):
            type(self).job_posts += 1
            return self.send({"id": data["capability"], "status": "queued"})
        self.send({"error": "unknown fixture endpoint"}, 404)

    def do_GET(self):
        base = f"http://127.0.0.1:{self.server.server_port}"
        if self.path == "/stats":
            return self.send({"job_posts": type(self).job_posts})
        if "/text-to-3d/" in self.path:
            return self.send({"status": "SUCCEEDED", "model_urls": {"glb": base + "/asset.glb"}})
        if "/jobs/" in self.path:
            kind = self.path.rsplit("/", 1)[-1]
            extension = {
                "world": ".glb",
                "model3d": ".glb",
                "video": ".mp4",
                "image": ".png",
                "speech": ".wav",
            }.get(kind)
            return self.send(
                {
                    "status": "succeeded",
                    "text": "bridge text",
                    "artifacts": (
                        [{"url": base + "/asset" + extension, "kind": kind, "extension": extension}]
                        if extension
                        else []
                    ),
                }
            )
        if self.headers.get("Authorization"):
            return self.send({"error": "credentials must not be sent to asset downloads"}, 403)
        if self.path == "/asset.glb":
            return self.send(triangle_glb(), content_type="model/gltf-binary")
        if self.path == "/asset.png":
            return self.send(PNG, content_type="image/png")
        if self.path == "/asset.wav":
            return self.send(wav_bytes(), content_type="audio/wav")
        if self.path == "/asset.mp4":
            fixture = Path(__file__).with_name("video.mp4")
            return self.send(
                fixture.read_bytes() if fixture.exists() else b"fixture-video",
                content_type="video/mp4",
            )
        self.send({"error": "not found"}, 404)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    print(server.server_port, flush=True)
    server.serve_forever()
