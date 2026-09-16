"""Native media adapters and a documented, vendor-neutral asynchronous jobs bridge."""
import base64
import ipaddress
from pathlib import Path
import socket
import time
from urllib.parse import quote, urlsplit
import uuid
from .http import HTTPClient, ProviderError

EXTENSIONS = {"model3d": {".glb", ".obj", ".fbx", ".stl"},
              "world": {".glb", ".obj", ".fbx"},
              "image": {".png", ".jpg", ".jpeg", ".webp"},
              "video": {".mp4", ".webm", ".mov"},
              "speech": {".mp3", ".wav", ".ogg", ".flac"}}
MAX_ASSET_BYTES = 100_000_000


def upload_inputs(client, inputs):
    """Bridge v2 receives uploaded asset handles, never unusable local filenames."""
    from .attachments import attachment, verified_bytes
    uploaded = {}
    def convert(item):
        if isinstance(item, list):
            return [convert(v) for v in item]
        if not isinstance(item, dict):
            return item
        if 'path' in item and 'kind' in item:
            ref = item if item.get('sha256') else attachment(item['path'], role=item.get('role','dependency'))
            key = ref['sha256']
            if key not in uploaded:
                raw = verified_bytes(ref)
                response = client.call(client.config.endpoint('/assets'), {'name':ref['name'], 'mime':ref['mime'],
                    'sha256':key, 'data_base64':base64.b64encode(raw).decode()})
                if not isinstance(response, dict) or not isinstance(response.get('id'), str) or not response['id']:
                    raise ProviderError('Bridge asset upload returned no ID')
                uploaded[key] = response['id']
            return {'asset_id':uploaded[key], 'kind':ref['kind'], 'role':ref.get('role','reference'), 'sha256':key}
        return {k:convert(v) for k,v in item.items()}
    return convert(inputs or [])


def validate_asset_url(url, provider_url):
    parts, origin = urlsplit(url), urlsplit(provider_url)
    if parts.username or parts.password or parts.fragment or not parts.hostname:
        raise ProviderError("Invalid generated asset URL")
    same_origin = (parts.scheme, parts.hostname, parts.port) == (origin.scheme, origin.hostname, origin.port)
    if parts.scheme != "https" and not (same_origin and parts.scheme == "http"):
        raise ProviderError("Generated asset downloads require HTTPS")
    if not same_origin:
        try:
            addresses = socket.getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
        except OSError:
            raise ProviderError("Cannot resolve the generated asset host") from None
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ProviderError("Asset URL points to a non-public network address")
    return url


def save_asset(raw, output_dir, kind, extension, name="asset"):
    if extension.lower() not in EXTENSIONS.get(kind, set()):
        raise ProviderError(f"Unsupported {kind} artifact format: {extension}")
    if not raw or len(raw) > MAX_ASSET_BYTES:
        raise ProviderError("Generated asset is empty or exceeds 100 MB")
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    path = output / (uuid.uuid4().hex + extension.lower())
    partial = path.with_suffix(path.suffix + ".part")
    try:
        partial.write_bytes(raw)
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)
    return {"kind": kind, "path": str(path), "name": str(name)[:120], "bytes": len(raw)}


def download_asset(client, item, output_dir, default_kind):
    if not isinstance(item, dict):
        raise ProviderError("Invalid artifact descriptor")
    kind = item.get("kind", default_kind)
    url = validate_asset_url(item.get("url", ""), client.config.base_url)
    extension = item.get("extension") or Path(urlsplit(url).path).suffix.lower()
    if extension not in EXTENSIONS.get(kind, set()):
        raise ProviderError("Asset format is unsupported; use a self-contained GLB for 3D scenes")
    raw = client.call(url, binary=True, authenticated=False, max_bytes=MAX_ASSET_BYTES)
    return save_asset(raw, output_dir, kind, extension, item.get("name", "asset"))


def _wait(client, url, initial, complete_states, failed_states):
    deadline = time.monotonic() + client.config.timeout
    result = initial
    while str(result.get("status", "")).lower() not in complete_states:
        status = str(result.get("status", "")).lower()
        if status in failed_states:
            raise ProviderError("Remote generation job failed or was cancelled")
        if time.monotonic() >= deadline:
            raise ProviderError("Remote generation timed out; check the provider before submitting again")
        time.sleep(max(0.1, min(10.0, float(client.config.options.get("poll_interval", 2)))))
        result = client.call(url)
        if not isinstance(result, dict):
            raise ProviderError("Invalid remote job status")
    return result


def generate(config, capability, prompt, output_dir, input_path="", inputs=None):
    config.validate()
    client = HTTPClient(config)
    artifacts, content = [], ""
    options = config.options
    if config.protocol != 'bridge' and any(isinstance(i,dict) and i.get('sha256') and i.get('path') for i in (inputs or [])):
        raise ProviderError('This native adapter does not support binary conditioning. Use an Async Jobs Bridge for attached image/3D/video inputs.')
    if config.protocol == "images":
        payload = {"model": config.model, "prompt": prompt, "n": 1}
        for key in ("size", "quality", "response_format", "output_format", "background"):
            if key in options:
                payload[key] = options[key]
        body = client.call(config.endpoint("/images/generations"), payload, max_bytes=32_000_000)
        item = body["data"][0]
        if item.get("b64_json"):
            raw = base64.b64decode(item["b64_json"], validate=True)
            ext = ".jpg" if options.get("output_format") == "jpeg" else "." + options.get("output_format", "png")
            artifacts.append(save_asset(raw, output_dir, "image", ext, "Generated image"))
        else:
            artifacts.append(download_asset(client, {"url": item["url"], "extension": ".png"}, output_dir, "image"))
    elif config.protocol == "speech":
        fmt = options.get("response_format", "mp3")
        audio_extensions = {"mp3": ".mp3", "wav": ".wav", "opus": ".ogg", "flac": ".flac"}
        if fmt not in audio_extensions:
            raise ProviderError("Choose mp3, wav, opus or flac audio output")
        payload = {"model": config.model, "input": prompt,
                   "voice": options.get("voice", "alloy"), "response_format": fmt}
        raw = client.call(config.endpoint("/audio/speech"), payload, binary=True,
                          max_bytes=MAX_ASSET_BYTES)
        artifacts.append(save_asset(raw, output_dir, "speech", audio_extensions[fmt], "Generated speech"))
    elif config.protocol == "transcription":
        path = Path(input_path)
        if not path.is_file() or path.stat().st_size > 25_000_000:
            raise ProviderError("Choose an audio input file no larger than 25 MB")
        if path.suffix.lower() not in {".wav", ".mp3", ".mp4", ".m4a", ".ogg", ".webm", ".flac"}:
            raise ProviderError("Unsupported audio input format")
        boundary = "AMA" + uuid.uuid4().hex
        data = bytearray()
        for key, value in {"model": config.model, "response_format": "json"}.items():
            data.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        data.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="input{path.suffix}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode())
        data.extend(path.read_bytes())
        data.extend(f'\r\n--{boundary}--\r\n'.encode())
        body = client.call(config.endpoint("/audio/transcriptions"), data=bytes(data),
                           content_type="multipart/form-data; boundary=" + boundary)
        content = body.get("text", "")
        if not isinstance(content, str) or not content:
            raise ProviderError("Transcription returned no text")
    elif config.protocol == "meshy":
        endpoint = config.endpoint("/openapi/v2/text-to-3d")
        payload = {"mode": "preview", "prompt": prompt, "art_style": options.get("art_style", "realistic")}
        for key in ("ai_model", "topology", "target_polycount", "should_remesh"):
            if key in options:
                payload[key] = options[key]
        job = client.call(endpoint, payload)
        ident = job.get("result")
        if not isinstance(ident, str) or not ident:
            raise ProviderError("Meshy returned no task ID")
        result = _wait(client, endpoint + "/" + quote(ident, safe=""), {},
                       {"succeeded"}, {"failed", "canceled", "cancelled", "expired"})
        if options.get("refine", True):
            refined = client.call(endpoint, {"mode": "refine", "preview_task_id": ident,
                                             "enable_pbr": True})
            ident = refined.get("result")
            if not isinstance(ident, str) or not ident:
                raise ProviderError("Meshy returned no refine task ID")
            result = _wait(client, endpoint + "/" + quote(ident, safe=""), {},
                           {"succeeded"}, {"failed", "canceled", "cancelled", "expired"})
        artifacts.append(download_asset(client, {"url": result["model_urls"]["glb"],
                                                 "extension": ".glb"}, output_dir, "model3d"))
    elif config.protocol == "bridge":
        endpoint = config.endpoint("/jobs")
        conditioned_inputs = upload_inputs(client, inputs)
        job = client.call(endpoint, {"schema_version": 2, "capability": capability,
                                    "model": config.model, "prompt": prompt,
                                    "inputs": conditioned_inputs, "options": options})
        if not isinstance(job, dict):
            raise ProviderError("Bridge returned invalid job data")
        if job.get("status") != "succeeded":
            ident = job.get("id")
            if not isinstance(ident, str) or not ident:
                raise ProviderError("Bridge returned no job ID")
            job = _wait(client, endpoint + "/" + quote(ident, safe=""), job,
                        {"succeeded"}, {"failed", "cancelled", "canceled"})
        items = job.get("artifacts", [])
        if not isinstance(items, list) or len(items) > 8:
            raise ProviderError("Bridge must return at most eight artifact descriptors")
        artifacts = [download_asset(client, item, output_dir, capability) for item in items]
        content = job.get("text", "")
        if capability in EXTENSIONS and not artifacts:
            raise ProviderError("Bridge finished without a downloadable artifact")
        if capability in {"chat", "transcription"} and not content:
            raise ProviderError("Bridge finished without text")
    else:
        raise ProviderError(f"Protocol {config.protocol} cannot generate {capability}")
    return {"content": content, "artifacts": artifacts, "error": "",
            "prompt_tokens": 0, "completion_tokens": 0, "cost": None}
