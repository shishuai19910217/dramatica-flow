<div align="center">

# Dramatica-Flow

### AI-Powered Long-Form Novel Writing System

**Make AI understand stories, not just write text.**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Quick Start](#quick-start) · [Core Features](#core-features) · [Architecture](#architecture) · [Demo](#demo) · [API Documentation](#api-documentation)

---

<p align="center">
  <img src="https://img.shields.io/badge/Theory-Dramatica%20Narrative-9C27B0?style=for-the-badge" alt="Dramatica Theory"/>
  &nbsp;
  <img src="https://img.shields.io/badge/Engine-5%20Layer%20Agent%20Pipeline-FF9800?style=for-the-badge" alt="5-Layer Agent Pipeline"/>
  &nbsp;
  <img src="https://img.shields.io/badge/Narrative-Multi%20Threaded-2196F3?style=for-the-badge" alt="Multi-thread Narrative"/>
  &nbsp;
  <img src="https://img.shields.io/badge/Model-DeepSeek%2B%20Ollama-4CAF50?style=for-the-badge" alt="LLM Support"/>
</p>

</div>

<p align="center">
  <img src="docs/screenshots/worldview.png" alt="Worldbuilding Configuration" width="860"/>
</p>
<p align="center"><i>Worldbuilding — Visual configuration of characters, factions, locations, and world rules</i></p>

---

## What is Dramatica-Flow?

Dramatica-Flow is an **AI-assisted novel writing platform** for web novel authors and professional writers. Unlike simple "AI text generators," it is an intelligent writing system built on **Dramatica narrative theory**—

The system abstracts novel writing into a quantifiable, trackable, and auditable engineering process. Through **causal chain management, emotional arc tracking, hook systems, relationship networks, multi-threaded narrative, and information boundaries**, it ensures AI-generated content has genuine narrative logic and internal consistency, rather than being loose piles of events.

### Key Differences from Generic AI Writing Tools

| Dimension | Generic AI Writing Tools | **Dramatica-Flow** |
|-----------|-------------------------|----------------------|
| Narrative Logic | Paragraph-by-paragraph, no global causality | **Forced causal chain modeling**: Every event must answer "why → what happened → what followed" |
| Character Consistency | Prone to OOC (Out of Character) | **Information boundary system**: Characters only know what they've seen/heard, eliminating omniscient perspective contamination |
| Long-Form Coherence | Frequent contradictions | **World state snapshots + truth files**: State accumulates between chapters, never lost |
| Hook Management | None | **Hook lifecycle**: Plant → track → warn → resolve, automatic overdue reminders |
| Quality Control | No auditing | **3-layer audit mechanism**: Rule verification → narrative audit → revision loop (max 2 rounds) |
| Multi-Threaded Narrative | None | **Global timeline**: Multi-thread scheduling, cross-thread awareness, inactive thread warnings |

---

## Core Features

### 1. Causal Chain Engine — The Skeleton of Story

Every event follows strict causal structure:

```
Ch.1: Breakup in Public
├── Cause     : The Mu family believes Lin Chen (useless spiritual root) can't bring benefits
├── Event     : Lin Chen suffers public humiliation
├── Effect    : Lin Chen makes a three-year pact
└── Decision  : Lin Chen ventures alone into Qingfeng Mountain, risking everything to cultivate
```

AI writing is forced to inject causal chain context, ensuring every chapter is a natural continuation of previous causes, not randomly concatenated scenes.

### 2. Smart Hook System — Unforgotten Promises

Automatically manages four types of narrative promises:

| Type | Description | Example |
|------|-------------|---------|
| **Foreshadow** | Hidden setup | A mysterious jade pendant in Ch.3 reveals identity in Ch.28 |
| **Promise** | Reader commitment | "Three-year pact" must be fulfilled within three years |
| **Mystery** | Unsolved puzzle | Where did the vanished spiritual power in the secret room go? |
| **Conflict** | Unresolved tension | When will the two factions' shadow war erupt? |

The system automatically tracks hook status and warns when overdue, eliminating "plot holes left unfilled."

### 3. Emotional Arcs — Visual Character Growth

1-10 intensity emotion tracking per character, supporting Dramatica's dual-need model: **external goals** (visible, quantifiable) vs. **internal desires** (what the character truly needs but doesn't realize).

```
Lin Chen's emotional curve:
  Humiliation(9) → Anger(8) → Shock(7) → Resolve(7) → Confidence(6) → Fear(9) → Determination(10)
                                                                     ↑
                                                               Character arc complete
```

### 4. Character Relationship Network — Dynamic Interpersonal Graph

Relationship strength ranges from **-100 (sworn enemies) to +100 (sworn allies)**, automatically updated after every event:

```python
# Relationship change examples
"Lin Chen-Mu Xue": +20, Mu Xue sees Lin Chen risking injury to save her
"Lin Chen-Xiao Tian": -30, Xiao Tian's secret alliance with demons exposed
```

### 5. Multi-Threaded Narrative — Global Timeline Scheduling

Supports **main plot, subplot, parallel, and flashback** threads, each with independent:
- POV character and character group
- Goal arc and growth trajectory
- Word count weight (automatic allocation adjustment)
- Inactivity warning (automatically alerts after 5+ inactive chapters)

Global timeline records "who, when, where, what" — the "God's view" ledger for multi-threaded narratives.

### 6. Information Boundaries — No Omniscient Contamination

Each character maintains independent knowledge records:

```python
@dataclass
class KnownInfoRecord:
    character_id: str      # Who knows
    info_key: str          # What information
    content: str           # Specific details
    learned_in_chapter: int    # In which chapter learned
    source: Literal["witnessed", "hearsay", "deduced", "document"]  # Information source
```

**Characters cannot know what they haven't seen** — this is one of the most fundamental differences between Dramatica-Flow and other AI writing tools.

---

## Architecture

### 5-Layer Agent Writing Pipeline

```
Snapshot Backup
    ↓
① Architect Agent — Plan blueprint (causal chain context + previous summary + hook status + cross-thread awareness)
    ↓
② Writer Agent — Generate main text + post-writing settlement table (position/emotion/relationship/hook changes)
    ↓
③ Post-Write Validator — Zero-LLM hard rule checks (word count, forbidden words, format)
    ↓ error → spot-fix
④ Auditor Agent — Narrative quality audit (temperature=0 for objective consistency)
    ↓ critical → Reviser Agent → re-audit (max 2 rounds)
⑤ Causal Chain Extractor — Extract causal relationships from text → write to world state
    ↓
Summary Generator — Chapter summary injects into truth files
    ↓
State Settlement — Apply post-writing settlement table → world_state.json
    ↓
Timeline + Thread Status Update
```

### Dramatica Theory Integration

System includes complete **Dramatica character role system**:

| Role | Chinese | Narrative Purpose |
|------|---------|------------------|
| Protagonist | 主角 | Core force driving the story forward |
| Antagonist | 反派 | Adversary opposing the protagonist's goals |
| Impact Character | 冲击者 | Key figure changing protagonist's perception |
| Guardian | 守护者 | Mentor/guide |
| Contagonist | 阻碍者 | Appears helpful but actually delays |
| Sidekick | 伙伴 | Loyal supporter |
| Skeptic | 怀疑者 | Questioning and opposing voice |

And **10 dramatic function beats**: Setup, Inciting Incident, Turning Point, Midpoint, Crisis, Climax, Reveal, Decision, Consequence, Transition.

### Tech Stack

```
┌──────────────────────────────────────────────────┐
│                   Web UI Layer                    │
│   Modern SPA · 7 feature modules · Timeline view  │
├──────────────────────────────────────────────────┤
│                  REST API Layer                   │
│   FastAPI · 50+ endpoints · Pydantic validation   │
├──────────────────────────────────────────────────┤
│                Agent Pipeline Layer               │
│   Architect · Writer · Auditor · Reviser · Summary│
├──────────────────────────────────────────────────┤
│              Narrative Engine Layer               │
│   Causal chain · Hook system · Emotional arcs    │
│   Relationships · Multi-threaded narrative      │
│   Information boundaries · World state           │
├──────────────────────────────────────────────────┤
│                LLM Abstraction Layer              │
│   DeepSeek API · Ollama local · OpenAI compatible│
└──────────────────────────────────────────────────┘
```

---

## Demo

### Web UI — One-Stop Creative Console

After starting the service, visit `http://localhost:8766` for a complete visual management interface:

**7 Feature Modules:**

| Module | Functionality |
|--------|--------------|
| **Overview Panel** | Book progress, chapter statistics, hook status overview |
| **Story Configuration** | Character/faction/location/world rule creation & editing |
| **Outline Management** | AI-generated story outlines, act filtering, sequence planning, linked continuation |
| **Chapter Writing** | AI writing, manual revision, audit results viewing |
| **Story Tracking** | Real-time visualization of causal chains, emotional arcs, hooks, relationships |
| **Timeline** | Multi-thread narrative swimlane view, character activity tracking, zoom navigation |
| **System Settings** | LLM backend switching, model configuration |

### Worldbuilding Configuration

Visually build your story world in Web UI — character settings (Dramatica roles, dual needs, personality locking), faction relationships, location network, world rules, providing complete worldview context for AI writing.

<p align="center">
  <img src="docs/screenshots/worldview-detail.png" alt="Worldbuilding Configuration Details" width="860"/>
</p>

### Outline Planning

Automatically generate three-act structure outlines based on Dramatica theory, with support for act filtering, sequence planning, and dramatic function beat labeling. After outline completion, one-click generation of chapter-by-chapter outlines, clarifying narrative tasks and emotional goals for each chapter.

<p align="center">
  <img src="docs/screenshots/outline.png" alt="Outline Planning" width="860"/>
</p>

### Linked Outline Continuation

Story outlines and chapter outlines support **linked continuation**: when story outline continues with new sequences, chapter outline continuation automatically detects unexpanded sequences, prioritizing planning based on new sequence's narrative goals, key events, and ending hooks rather than blind self-rolling. When all sequences are covered, automatically falls back to free continuation mode based on existing chapter outline tail.

### AI Writing

Based on outline and chapter outlines, AI automatically generates chapter content according to causal chain context, previous summary, and hook status. After writing completion, system automatically extracts settlement table (character position/emotional changes/relationship changes/hook toggles) and updates world state.

<p align="center">
  <img src="docs/screenshots/writing.png" alt="AI Writing Interface" width="860"/>
</p>

### Audit & Revision

Three-layer audit automatically triggers after each chapter completion: **Rule verification** (word count/forbidden words/format hard rules) → **Narrative audit** (causal consistency/character OOC/hook omission dimensions) → **Revision loop** (critical issues auto-revised, max 2 rounds).

<p align="center">
  <img src="docs/screenshots/audit.png" alt="Audit Results" width="860"/>
</p>

### Timeline Swimlane View

Independent timeline page (`/timeline`) provides:

- **Multi-thread swimlanes**: Each narrative thread has independent swimlane, events distributed by chapter
- **Chapter range slider**: Drag to focus on specific chapter interval, quick navigation for long works
- **Mini overview heat bar**: Top shows full work event density, one-click jump to interesting areas
- **Same-chapter event staggering**: Multiple events in same chapter automatically vertically staggered to avoid overlap
- **Key node filtering**: Filter/highlight by event type (hook planting/resolve, emotional turns, etc.)
- **Character activity tracking**: Shows character positions and actions in each chapter
- **Zoom control**: Freely adjust swimlane density for different lengths
- **Act structure background**: Three-act structure visual sections

<p align="center">
  <img src="docs/screenshots/timeline.png" alt="Multi-Thread Narrative Timeline" width="860"/>
</p>
<p align="center"><i>Multi-Thread Narrative Timeline — Swimlane view showing thread event distribution, character activity, and key nodes</i></p>

---

## Quick Start

### Prerequisites

- **Python** >= 3.11 ([Download](https://www.python.org/downloads/), check "Add Python to PATH" during installation)
- **LLM Backend** (choose one): DeepSeek API key or Ollama local environment

### Installation

```bash
# Clone repository
git clone https://github.com/ydsgangge-ux/dramatica-flow.git
cd dramatica-flow
```

**One-Click Installation (Recommended):**

| OS | Action |
|----|--------|
| Windows | Double-click `install.bat` |
| Linux / macOS | `bash install.sh` |

Script automatically handles all steps:
- Checks Python version (prompts download if <3.11)
- Installs all dependencies (auto-fills missing packages)
- Creates `.env` config file (if doesn't exist)

**Manual Installation (if script fails):**

```bash
python -m pip install -e .
```

### Configure LLM Backend

After installation, open `.env` file in project root with a text editor and configure **one of the following**:

**Option A: DeepSeek API (Best Quality, Paid)**

1. Register at [DeepSeek Platform](https://platform.deepseek.com) and get API Key
2. Replace `sk-xxx` with your real API Key in `.env`

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_real_api_key
```

**Option B: Ollama Local Model (Completely Free)**

1. Download and install from [ollama.ai](https://ollama.ai)
2. Run `ollama pull qwen2.5` in terminal to download model
3. Update `.env`:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5
```

> For detailed configuration, see [Ollama Guide](docs/OLLAMA_GUIDE.md)

### Launch

```bash
# Windows: Double-click `启动服务器.bat` or `启动网页界面.bat` (auto-opens browser)
# Linux/macOS: python -m uvicorn core.server:app --reload --port 8766

# Or manually:
python -m uvicorn core.server:app --reload --port 8766
```

Then visit **http://localhost:8766** to get started.

### Import Existing Novel

If you already have a completed novel (like 100k words), you can extract worldview through external LLM and import:

1. Open [Extraction Prompt Template](templates/novel_extract_prompt.md), copy prompt and JSON format instructions
2. Send prompt + full novel text to external LLM (like [DeepSeek Chat](https://chat.deepseek.com), free, supports very long contexts)
3. Copy JSON output from LLM
4. In Web UI **Step 3 Worldbuilding Configuration**, click **"Import JSON"** and paste

---

## Writing Workflow

```
① Create Book        df book --title "My Novel" --genre "Xuanhuan" --chapters 100
       ↓
② Initialize Config  Configure characters, factions, locations, world rules in Web UI
       ↓
③ Generate Outline   AI automatically generates three-act structure outline based on Dramatica theory
       ↓
④ Chapter Writing    AI writing → rule verification → narrative audit → revision loop
       ↓
⑤ Story Tracking     Real-time monitoring of causal chains, emotional arcs, hook status
       ↓
⑥ Export Final       One-click export to Markdown / full text review
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `df init <name>` | Initialize project |
| `df book --title "My Novel" --genre "Xuanhuan" --chapters 100` | Create new book |
| `df setup init-templates <book>` | Initialize config templates |
| `df setup load <book>` | Load config into world state |
| `df write <book>` | AI write next chapter |
| `df write <book> --count 5` | Write 5 chapters consecutively |
| `df audit <book> <chapter>` | Audit specific chapter |
| `df revise <book> <chapter>` | Revise chapter |
| `df status <book>` | View book status |
| `df export <book>` | Export full book |
| `df doctor` | Diagnose project configuration |

---

## API Documentation

System provides **50+ REST API endpoints**, complete coverage of creative workflow.

### Book Management
```
GET    /api/books                            # Book list
POST   /api/books                            # Create book
GET    /api/books/{id}                       # Book details
DELETE /api/books/{id}                       # Delete book
```

### Story Configuration
```
GET    /api/books/{id}/setup/status          # Config status
POST   /api/books/{id}/setup/init            # Initialize config templates
GET    /api/books/{id}/setup/{type}          # Get config (characters/factions/locations/events)
PUT    /api/books/{id}/setup/{type}          # Update config
POST   /api/books/{id}/setup/load            # Load config into world state
```

### AI Writing Core
```
POST   /api/books/{id}/ai-generate/outline            # AI generate story outline
POST   /api/books/{id}/ai-continue/outline            # AI continue story outline
POST   /api/books/{id}/ai-generate/chapter-outlines   # AI generate chapter outlines
POST   /api/books/{id}/continue-writing               # Continue chapter outlines (linked story outline)
POST   /api/books/{id}/ai-generate/detailed-outline   # AI generate detailed chapter outline
POST   /api/books/{id}/ai-generate/chapter-content    # AI generate chapter content
POST   /api/books/{id}/ai-rewrite-segment             # AI rewrite specific segment
POST   /api/action/write                              # Execute writing pipeline
POST   /api/action/audit                              # Execute audit
POST   /api/action/revise                             # Execute revision
POST   /api/action/export                             # Export full book
```

### Story Tracking
```
GET    /api/books/{id}/causal-chain          # Causal chain
GET    /api/books/{id}/emotional-arcs        # Emotional arcs
GET    /api/books/{id}/hooks                 # Hook list
GET    /api/books/{id}/relationships         # Relationship network
GET    /api/books/{id}/threads               # Narrative threads
GET    /api/books/{id}/timeline              # Global timeline
```

### Story Analysis
```
POST   /api/books/{id}/extract-from-novel    # Extract worldview from existing novel
POST   /api/books/{id}/extract-story-state   # Extract story state (characters/events/relationships)
POST   /api/books/{id}/three-layer-audit     # Three-layer audit
GET    /api/books/{id}/audit-results         # Audit results list
```

### System Configuration
```
GET    /api/settings                         # Get settings
POST   /api/settings                         # Update settings
GET    /api/settings/status                  # Settings status check
```

---

## Project Structure

```
dramatica-flow/
├── core/                           # Core engine
│   ├── agents/                     # AI Agents (Architect/Writer/Auditor/Reviser/Summary)
│   ├── llm/                        # LLM abstraction layer (DeepSeek + Ollama)
│   ├── narrative/                  # Narrative engine (outline parsing, causal chain extraction)
│   ├── state/                      # State management (world state, truth files, snapshots)
│   ├── types/                      # Data type definitions (characters/events/causal chains/hooks...)
│   ├── validators/                 # Content validators (zero-LLM hard rules)
│   ├── pipeline.py                 # 5-layer writing pipeline
│   └── server.py                   # FastAPI service (50+ endpoints)
├── cli/                            # CLI tools
│   └── main.py                     # CLI entry (Typer)
├── books/                          # Book data directory
├── templates/                      # Config templates + extraction prompts
├── tests/                          # Test suite (89 cases)
├── docs/                           # Documentation
│   ├── CHANGELOG.md                # Changelog
│   ├── OLLAMA_GUIDE.md             # Ollama configuration guide
│   ├── QUICKSTART.md               # Quick start
│   ├── PROJECT_STATUS.md           # Project status
│   ├── ARCHITECTURE_DESIGN.md      # Architecture design document
│   ├── FUNCTIONAL_DESIGN.md        # Functional design document
│   ├── METHODS_DOCUMENTATION.md    # Methodology documentation
│   └── screenshots/                # UI screenshots
├── dramatica_flow_web_ui.html      # Web UI main interface
├── dramatica_flow_timeline.html    # Timeline swimlane view
├── install.bat                     # Windows one-click install
├── install.sh                      # Linux/macOS one-click install
├── 启动服务器.bat                   # Windows start service
├── 启动网页界面.bat                  # Windows start and open browser
├── .env.example                    # Environment variable template
├── pyproject.toml                  # Project config
└── setup.py                        # Package installation entry
```

---

## Testing

```bash
# Run all tests
python run_tests.py

# Or use pytest
python -m pytest tests/ -v
```

---

## Related Documents

- [Quick Start Guide](docs/QUICKSTART.md) — Finish your first creation in 5 minutes
- [Ollama Configuration Guide](docs/OLLAMA_GUIDE.md) — Detailed local model setup
- [Changelog](docs/CHANGELOG.md) — Version feature changes
- [Project Status](docs/PROJECT_STATUS.md) — Development progress and roadmap
- [Architecture Design Document](docs/ARCHITECTURE_DESIGN.md) — System architecture explanation
- [Functional Design Document](docs/FUNCTIONAL_DESIGN.md) — Functional design description
- [Methodology Documentation](docs/METHODS_DOCUMENTATION.md) — Writing methodology details

---

## Technical Specifications

| Item | Specification |
|------|--------------|
| Language | Python 3.11+ |
| Web Framework | FastAPI |
| LLM Interface | OpenAI SDK (compatible protocol) |
| Data Validation | Pydantic v2 |
| CLI Framework | Typer + Rich |
| Test Framework | pytest + pytest-asyncio |
| Frontend | Vanilla HTML/CSS/JS (zero build dependencies) |
| Supported Models | DeepSeek, Ollama (qwen2.5/llama3.1/mistral, etc.) |

---

## Contributing

We welcome any form of contribution! Please follow these steps:

1. Fork this repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

Please ensure your code follows project coding style and passes all tests.

---

## License

MIT License — see [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [Dramatica Theory](https://dramatica.com/) — Narrative theory framework
- [FastAPI](https://fastapi.tiangolo.com/) — High-performance web framework
- [Ollama](https://ollama.ai/) — Local LLM runtime
- [OpenAI SDK](https://github.com/openai/openai-python) — LLM interface standard
