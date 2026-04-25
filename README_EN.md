> 🇨🇳 [中文](README.md) | 🇺🇸 English

# AI Modeling Assistant for Blender

> An AI-powered 3D modeling copilot that transcends primitive-stacking — engineered for production-grade asset creation.

## Overview

A sophisticated Blender addon that transmutes natural language descriptions into high-fidelity Python modeling scripts, subsequently executing them within the Blender environment. Architectured for universal compatibility with any OpenAI-compliant API — encompassing OpenAI, DeepSeek, Qwen, Ollama (local inference), and beyond.

## Distinguishing Features

### 🧠 Intelligent Modeling Paradigm

Unlike rudimentary approaches that merely aggregate basic primitives, the AI undergoes a **quintessential cognitive pipeline** prior to code synthesis:

1. **Design Decomposition** — Dissecting the request into discrete geometric constituents, delineating the topological strategy for each component
2. **Proportion Calibration** — Anchoring dimensions to real-world metrics (meters), ensuring anthropometric and architectural fidelity
3. **Topology Strategization** — Selecting optimal modeling methodologies: extrusion, lathe, subdivision, boolean operations, curve-based workflows
4. **Material Stratagem** — Assigning physically-based rendering materials calibrated to real-world surface properties
5. **Quality Assurance** — Automated verification of polygon density, normal orientation, and orphaned geometry

The system prompt incorporates **eight modeling techniques** with exhaustive code exemplars:
- Extrusion modeling (hard-surface fabrication)
- Spin/lathe operations (vessels, columns, rotational symmetry)
- Subdivision surface workflows (organic sculpting)
- Boolean operations (complex geometric intersections)
- Curve + bevel pipelines (conduits, ornamental trim)
- Array + curve distribution (chains, fences, repetitive motifs)
- Proportional editing (organic deformation)
- Armature + skin modifier (arboreal structures, coral formations)

### 🔄 Multi-Pass Generation

For intricate models demanding superior craftsmanship, the **triple-pass generation pipeline** ensures iterative refinement:

| Pass | Objective |
|------|-----------|
| Pass 1 | **Foundation** — Establish correct macro-scale proportions and spatial relationships |
| Pass 2 | **Elaboration** — Infuse geometric intricacies: bevels, insets, extrusions, decorative embellishments |
| Pass 3 | **Refinement** — PBR material assignment, surface texturing via procedural nodes, final polish |

### ✏️ Iterative Refinement

Select an extant mesh → articulate desired modifications → the AI leverages bmesh operations to **sculpt upon the existing geometry** rather than regenerating from scratch. This preserves artistic intent while enabling progressive enhancement.

### 🛡️ Security Architecture

- SSL certificate verification perpetually enforced
- Sandboxed execution environment: AI-generated code is precluded from accessing `os`, `subprocess`, or the filesystem
- Malicious pattern interception (`eval`, `exec`, `open`, `__import__`, etc.)
- Whitelisted module registry: exclusively `bpy`, `bmesh`, `math`, `mathutils`, `random`

---

## Installation

### Method 1: Direct Addon Installation

1. Acquire `ai_modeling_assistant.py` from this repository
2. Navigate to Blender → Edit → Preferences → Add-ons
3. Select `Install...` → designate the downloaded `.py` file
4. Activate "AI Modeling Assistant" via the checkbox

### Method 2: Manual Directory Placement

Copy `ai_modeling_assistant.py` to the appropriate addons directory:
- **Windows:** `%APPDATA%\Blender Foundation\Blender\<version>\scripts\addons\`
- **macOS:** `~/Library/Application Support/Blender/<version>/scripts/addons/`
- **Linux:** `~/.config/blender/<version>/scripts/addons/`

Subsequently enable the addon within Blender's preferences.

### Compatibility Matrix

| Blender Version | Status |
|----------------|--------|
| 3.6.x | ✅ Fully Supported |
| 4.0.x | ✅ Fully Supported |
| 4.1.x+ | ✅ Fully Supported |

All API discrepancies between 3.x and 4.x (material node nomenclature, etc.) are automatically reconciled.

---

## Usage

### 1. API Configuration

Access the sidebar (`N` key) → **AI Model** tab → expand **API Settings**:

| Parameter | Description |
|-----------|-------------|
| **Preset** | Select a provider preset or "Custom" for bespoke configuration |
| **API URL** | Endpoint URL (auto-populated by presets) |
| **API Key** | Authentication credential |
| **Model** | Model identifier string |
| **Temperature** | Stochasticity coefficient (0.0 = deterministic, 2.0 = maximal entropy) |
| **Max Tokens** | Response length ceiling |

#### Supported API Presets

| Preset | Endpoint | Default Model |
|--------|----------|---------------|
| OpenAI | api.openai.com | gpt-4o-mini |
| DeepSeek | api.deepseek.com | deepseek-chat |
| Qwen (Alibaba) | dashscope.aliyuncs.com | qwen-plus |
| Zhipu (GLM) | open.bigmodel.cn | glm-4-flash |
| Moonshot | api.moonshot.cn | moonshot-v1-8k |
| SiliconFlow | api.siliconflow.cn | Qwen/Qwen2.5-7B |
| Groq | api.groq.com | llama-3.3-70b |
| Together AI | api.together.xyz | Llama-3.3-70B |
| OpenRouter | openrouter.ai | llama-3.3-70b |
| Ollama (Local) | localhost:11434 | llama3.1 |
| LM Studio (Local) | localhost:1234 | local-model |
| **Custom** | User-defined | User-defined |

> 💡 Local inference engines (Ollama/LM Studio) require no API key.

### 2. AI-Powered Modeling

1. Articulate your desired model in the text field (supports Chinese and English)
2. Invoke **"Send to AI"**
3. The AI's reasoning process and generated code are displayed
4. Execute via **"Execute Code"** to instantiate the model in your scene

#### Exemplar Prompts

```
A medieval longsword with an 80cm blade, cruciform guard, and leather-wrapped grip
```

```
A potion bottle with translucent glass containing luminescent blue liquid and a cork stopper
```

```
An oak tree approximately 3 meters tall with textured bark and a dense, verdant canopy
```

```
A Gothic-style breastplate with riveted embellishments and compound curvature surfaces
```

### 3. Iterative Refinement

1. Select an existing mesh object in the viewport
2. Describe the desired modifications
3. Invoke **"AI Refine"**
4. The AI modifies the existing geometry in-place, preserving the original object hierarchy

### 4. Multi-Pass Generation

For complex assets, invoke **"Multi-Pass Gen"**:
- Executes three sequential AI generation passes
- Each pass incrementally augments detail upon the preceding output
- Automatic post-processing culminates the pipeline

---

## Feature Compendium

### ⚡ Quick Build — Instant Prototyping

API-independent, one-click instantiation of pre-authored models:

| Icon | Asset | Description |
|------|-------|-------------|
| 🧑 | Human Male | Anthropometric base mesh |
| ⚔ | Sword | Medieval longsword |
| 🛡 | Shield | Round shield with boss |
| 💊 | Potion | Elixir vessel |
| 🪑 | Table | Four-legged table |
| 💺 | Chair | Chair with backrest |
| 🏠 | House | Residential structure |
| 🐉 | Dragon | Draconic juvenile |
| 💎 | Crystal | Crystalline cluster |
| 🌳 | Tree | Arboreal specimen |
| 🍄 | Mushroom | Mycological cluster |
| 💀 | Skeleton | Skeletal warrior |
| 👑 | Crown | Regal crown |
| 🏛 | Archway | Architectural arch |
| 📦 | Chest | Treasure chest |
| 🔥 | Torch | Illumination torch |

### 🎨 Material Library

Twenty-nine PBR material presets encompassing ubiquitous surface types:

| Category | Presets |
|----------|---------|
| **Metals** | Steel, Gold, Copper, Bronze, Aluminum |
| **Polymers** | White, Red, Blue, Green, Black |
| **Timber** | Oak, Pine, Dark |
| **Vitreous** | Clear, Tinted |
| **Elastomers** | Black, White |
| **Textiles** | Cotton, Silk |
| **Lithic** | Granite, Marble, Concrete |
| **Miscellaneous** | Ceramic, Leather (×2), Emissive (×3), Water, Skin |

### 🔧 Modifier Presets

Twenty-four modifier configurations for expeditious application: Subdivision Surface, Mirror (X/XY/XYZ), Array, Bevel, Solidify, Triangulate, Decimate, Boolean (Union/Intersect/Difference), Smooth, Lattice, Shrinkwrap, Cast, Wave, Displace, Screw, Wireframe, Skin.

### 📐 Parametric Templates

Eight parameterized templates with adjustable dimensions: Chair, Table, Sword, House, Tree, Humanoid, Pillar, Gear.

### 🦴 Armature Systems

- **Humanoid** — 24-bone bipedal skeleton (spinal column, extremities, digits)
- **Quadruped** — 20-bone tetrapod skeleton (equine, canine, feline)

### 🗺️ UV Unwrapping

Five projection methodologies: Smart UV, Angle-Based, Cube Projection, Cylinder, Sphere.

### 📊 Mesh Analytics

Comprehensive diagnostics: polygon count, vertex enumeration, non-manifold edges, orphaned vertices, n-gons, inverted normals, bounding box dimensions.

### ✅ Quality Assurance

Automated scene-wide mesh auditing with issue classification and one-click remediation.

### 🎬 Animation Systems

- **Walk Cycle** — Procedural locomotion cycle
- **Breathing** — Respiratory oscillation
- **Camera Orbit** — Parametric orbital cinematography

### 🌍 Procedural Generation

- **Terrain** — Parametric landscape sculpting (extent, tessellation, amplitude, seed)
- **Tree** — Algorithmic arboreal generation (trunk, canopy parameters)
- **Scatter** — Stochastic object distribution upon surfaces

### 📦 Batch Operations

- **Rename** — Prefix/suffix/find-replace/sequential nomenclature
- **Export** — FBX/OBJ/glTF/STL batch serialization

### 🎮 Engine Export Presets

Pre-configured export pipelines for Unity, Unreal Engine, and Godot with automatic coordinate system transformation and scale normalization.

### 🗃️ Asset Management

Registration, categorization, and检索 of scene assets.

### 📸 Version Control

Scene snapshot persistence with temporal versioning and comparative analysis.

### 🔍 Intelligent Selection

Material-based, non-manifold geometry, and orphaned element selection operators.

### 🧹 Hygiene Utilities

Deletion of empty objects, orphaned meshes, unused materials, and unreferenced images.

---

## Advanced Capabilities

### Conversational Continuity

The AI retains conversational context, enabling iterative refinement workflows:
- "Forge a sword" → AI generates
- "Widen the guard" → AI refines the prior output
- "Inscribe runes upon the blade" → Continues iterating

History is automatically compressed to circumvent context window limitations.

### Cost Analytics

Real-time token consumption tracking with expenditure estimation and resettable counters.

### Post-Processing Pipeline

Automated mesh hygiene: duplicate vertex dissolution, normal recalculation, orphaned geometry excision, and material assignment verification.

---

## Frequently Encountered Queries

**Q: The AI-generated model lacks fidelity. Remediation?**
- Employ a more capable model (GPT-4o, Claude 3.5 Sonnet)
- Utilize multi-pass generation for iterative enhancement
- Leverage AI Refine for progressive sculpting
- Furnish more granular prompts (dimensions, material specifications, stylistic references)

**Q: Is local inference viable?**
- Affirmative. Install Ollama or LM Studio, then designate the corresponding preset.
- Output quality correlates with model parameter count; 7B+ recommended.

**Q: Blender 4.x compatibility?**
- Fully supported. All API divergences between 3.x and 4.x are automatically handled.

**Q: Security posture?**
- AI-generated code executes within a sandboxed environment, precluded from filesystem access.
- Malicious patterns are systematically intercepted and neutralized.

---

## License

GPL-3.0

---

## Contributions

Issues and Pull Requests are enthusiastically welcomed.
