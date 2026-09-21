# Model provider contracts

Version 3.2: conversation, planner and code/review experts require a Chat Completions
profile so role-separated messages and actual images retain their meaning. Bridge
profiles handle media experts. Known remote job IDs are persisted and resumed via
GET; ambiguous submissions cannot be replayed automatically. See
[workflow lifecycle and recovery](WORKFLOW_LIFECYCLES.md).

`context_window` reserves room for output tokens. `vision_tokens_per_image` defaults
to 4096 and can be adjusted to the provider's documented accounting (256–65536).
The host budgets maintenance, planning, repair and review as well as conversation.

## Routing and configuration

Each enabled provider defines a protocol, base URL, model ID, capabilities, optional
expert assignments, timeout and JSON options. The first provider assigned to an expert
is preferred over an unrestricted provider. Models assigned to other experts are not
silently reused. Without enabled profiles, scene chat settings provide a fallback.

Capabilities: `chat`, `model3d`, `image`, `video`, `speech`, `transcription`, `world`, `vision`.
Expert IDs are in `core/agents.py`; `planner` and `conversation` are additional routing roles.
Workers receive JSON snapshots, never Blender objects.

## Native adapters

| Protocol | Base URL example | Endpoint | Result |
|---|---|---|---|
| `chat` | `https://api.openai.com/v1` / `http://localhost:11434/v1` | `/chat/completions` | text/code/plan |
| `images` | compatible service's `/v1` root | `/images/generations` | base64 or URL image |
| `speech` | compatible service's `/v1` root | `/audio/speech` | audio bytes |
| `transcription` | compatible service's `/v1` root | `/audio/transcriptions` | multipart audio → text |
| `meshy` | `https://api.meshy.ai` | `/openapi/v2/text-to-3d` + polling | preview + optional refined GLB |

Use a model identifier supported by your actual service. Meshy uses its API default
unless `ai_model` is supplied. Useful chat options for models requiring them:

```json
{"token_field":"max_completion_tokens","omit_temperature":true}
```

Default chat sends `max_tokens` and `temperature`. Image options: `size`, `quality`,
`response_format`, `output_format`, `background`. Speech options: `voice`,
`response_format` (`mp3`, `wav`, `opus`, `flac`; Opus is stored as `.ogg`). Transcription uploads the selected audio file,
up to 25 MB. Meshy options: `refine` (default true), `art_style`, `ai_model`,
`topology`, `target_polycount`, `should_remesh`, `poll_interval`.

Enable `vision` only for a chat model that supports image content parts. Images are
sent as actual data URLs, limited to 1 MB total source image data per request. Text
attachments are bounded UTF-8 references. 3D/audio/video attachments in ordinary chat
are manifest-only, explicitly marked as not interpreted. To reserve room for output
against a known model limit, set `context_window` in protocol options; the dialogue
builder subtracts the configured output limit and a margin. Without it, the user sets
the input-context budget explicitly. Compression and memory extraction use additional
model requests and their usage is counted. Native text-to-image and text-to-3D adapters
reject binary conditioning rather than silently discarding attached references.

Reference shapes: [Meshy Text-to-3D](https://docs.meshy.ai/en/api/text-to-3d),
[OpenAI Audio](https://developers.openai.com/api/reference/typescript/resources/audio).
An OpenAI-compatible service may implement only some of these endpoints.

## Async Jobs Bridge

The bridge is an explicit contract that a separate server must implement for the
target vendor/local engine. It is not a claim that every vendor already exposes this
API. With base URL `https://your-bridge.example/api`, submit:

```http
POST /api/jobs
Content-Type: application/json
Authorization: Bearer <configured-key>
```

```json
{
  "schema_version": 2,
  "capability": "video",
  "model": "your-model-id",
  "prompt": "Slow orbital camera move around the mechanical beacon",
  "inputs": [],
  "options": {"poll_interval": 2}
}
```

Before submitting conditioned jobs, the client uploads actual input bytes:

```http
POST /api/assets
Content-Type: application/json
Authorization: Bearer <configured-key>
```

```json
{"name":"sketch.png","mime":"image/png","sha256":"content-sha256","data_base64":"..."}
```

The server validates the hash, stores the asset for the authenticated user and returns
`{"id":"asset-123"}`. The job's `inputs` then contains
`{"asset_id":"asset-123","kind":"image","role":"reference","sha256":"..."}`.
Predecessor task result artifacts are recursively uploaded and converted to handles too.
The client verifies local hashes before upload, limits inputs to 25 MB each and avoids
duplicate uploads within a request. The bridge owns storage lifetime, vendor conversion,
authorization, quotas and cleanup. Do not implement public unauthenticated uploads.
Text-only jobs need no upload endpoint. This v2 contract replaces the old metadata-only
v1 behavior; upgrade a custom bridge before using conditioned inputs.

Initial result:

```json
{"id":"job-123","status":"queued"}
```

Poll `GET /api/jobs/job-123`. Running states: `queued`, `running`. Terminal states:
`succeeded`, `failed`, `cancelled`. Immediate success in the POST response is supported.

```json
{
  "id": "job-123",
  "status": "succeeded",
  "text": "Optional notes",
  "artifacts": [
    {
      "kind": "video",
      "url": "https://assets.example/clip.mp4?signature=...",
      "extension": ".mp4",
      "name": "Orbit clip"
    }
  ]
}
```

At most eight artifacts per job, 100 MB per file. Media jobs must return an artifact;
chat/transcription jobs require text. Downloads use HTTPS, or the same loopback HTTP
origin as a local provider. Cross-origin private-network addresses are rejected.
Provider Authorization headers are never sent to asset URLs; use signed URLs.
Redirects are rejected. Client-generated filenames prevent path traversal.

Supported artifact kinds:

- `model3d`: `.glb`, `.obj`, `.fbx`, `.stl`.
- `world`: `.glb`, `.obj`, `.fbx`.
- `image`: `.png`, `.jpg`, `.jpeg`, `.webp`.
- `video`: `.mp4`, `.webm`, `.mov`.
- `speech`: `.mp3`, `.wav`, `.ogg`, `.flac`.

Use self-contained GLB for complete scenes. Auxiliary OBJ/MTL/texture files are not
automatically downloaded. Remote scripts, archives and `.blend` files are not imported.

## Adding adapters

1. Declare protocol/capabilities in `core/config.py`.
2. Implement HTTP in `core/providers.py` or `core/media.py`.
3. Expose protocol settings in `blender/properties.py`.
4. Add fixture and transport tests; reuse `ProcessJob`, not persistent Blender threads.
5. Add explicit validation and a main-thread importer for any new artifact kind.
6. Document simulated versus real-service verification.

The fixture server is a test double, not a production bridge. Local cancellation does
not issue vendor-specific cancel/delete calls. Check remote task status before resubmission.
