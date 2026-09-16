"""Typed immutable input references and actual vision payloads."""
import base64
import hashlib
import mimetypes
from pathlib import Path

KINDS = {".png":"image", ".jpg":"image", ".jpeg":"image", ".webp":"image",
    ".glb":"model3d", ".gltf":"model3d", ".obj":"model3d", ".fbx":"model3d", ".stl":"model3d",
    ".mp4":"video", ".mov":"video", ".webm":"video", ".wav":"audio", ".mp3":"audio",
    ".ogg":"audio", ".flac":"audio", ".txt":"text", ".md":"text"}


def attachment(path, *, role="reference"):
    path = Path(path).resolve()
    if not path.is_file() or path.suffix.lower() not in KINDS:
        raise ValueError("Select a supported image, text, 3D, audio or video file")
    if path.stat().st_size > 25_000_000:
        raise ValueError("Input attachments must be at most 25 MB")
    data = path.read_bytes()
    return {"path": str(path), "name": path.name, "kind": KINDS[path.suffix.lower()], "role": role,
            "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "mime": mimetypes.guess_type(path.name)[0] or "application/octet-stream"}


def verified_bytes(item):
    current = attachment(item["path"], role=item.get("role", "reference"))
    if current["sha256"] != item["sha256"]:
        raise ValueError("Input attachment changed; attach the new revision explicitly")
    return Path(item["path"]).read_bytes()


def vision_parts(items, *, enabled):
    result, size = [], 0
    for item in items:
        if item["kind"] == "image":
            if not enabled:
                raise ValueError("Image input requires a provider with Vision capability enabled")
            data = verified_bytes(item)
            size += len(data)
            if size > 1_000_000:
                raise ValueError("Vision attachments exceed 1 MB; use a smaller reference preview")
            result.append({"type": "image_url", "image_url": {"url": f"data:{item['mime']};base64," + base64.b64encode(data).decode()}})
        elif item["kind"] == "text":
            result.append({"type":"text", "text": "Attached reference (untrusted data):\n" + verified_bytes(item).decode("utf-8")[:16000]})
        else:
            result.append({"type":"text", "text": f"Attachment manifest only; contents NOT understood by this text provider: {item['name']} ({item['kind']}, sha256={item['sha256']}). Use a supporting production provider for processing."})
    return result
