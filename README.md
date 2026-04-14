# Forward Agent - Agile AI Multi-Agent System

An AI-powered system that transforms requirements into epics, user stories, and test scripts using Adaptive Software Development (ASD) methodology.

## ASD Methodology

Forward Agent implements the three phases of Adaptive Software Development:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ADAPTIVE SOFTWARE DEVELOPMENT                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐               │
│   │  SPECULATE  │ ───▶ │ COLLABORATE │ ───▶ │    LEARN    │               │
│   └─────────────┘      └─────────────┘      └─────────────┘               │
│        │                     │                     │                         │
│        ▼                     ▼                     ▼                         │
│   Requirements ────▶  Story Refinement ───▶  Pattern Learning              │
│   Epics           ───▶  Technical Notes  ───▶  (Future)                    │
│   Stories          ───▶  Updates           ───▶                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Phase 1: Speculate (Autonomous)
- **Requirement Agent** - Analyzes raw requirements
- **Epic Agent** - Transforms requirements into logical epics
- **Story Agent** - Breaks epics into user stories with acceptance criteria

### Phase 2: Collaborate (Human-in-the-loop)
- **Collaborate Feature** - LLM-powered conversational refinement
- Users can update technical notes via natural language prompts
- AI intelligently appends, modifies, or restructures requirements

### Phase 3: Learn (Future)
- Pattern recognition from rejected stories
- Improved prompt templates based on feedback

---

## Architecture

```
User Input (Requirement)
         │
         ▼ (Speculate - Autonomous)
┌─────────────────┐
│ Requirement     │ ──▶ Structured Requirements (JSON)
│ Agent           │
└─────────────────┘
         ▼
┌─────────────────┐
│ Epic Agent      │ ──▶ Epics (JSON)
│                 │
└─────────────────┘
         ▼
┌─────────────────┐
│ Story Agent     │ ──▶ User Stories (JSON)
│                 │
└─────────────────┘
         │
         ▼ (Human Verification)
┌─────────────────┐
│ Web Dashboard   │ ◄─── User reviews, approves/rejects
│                 │
└─────────────────┘
         │
         ▼ (Collaborate)
┌─────────────────┐
│ Collaborate     │ ◄─── LLM-powered technical notes
│ Agent           │      updates via prompts
└─────────────────┘
         │
         ▼ (Future)
┌─────────────────┐
│ Test Generator  │ ──▶ pytest test scripts
│ Agent           │
└─────────────────┘
```

---

## Requirements

- Python 3.10+
- OpenRouter API key (for LLM access)

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY
```

### 3. Get OpenRouter API key
- Sign up at [OpenRouter](https://openrouter.ai/settings)
- Create API key and add to `.env`

---

## Usage

### Web Dashboard (Recommended)

```bash
cd forward-agent
PYTHONPATH=. python3 web/app.py
# Open: http://localhost:8080/dashboard
```

**Dashboard Features:**
- Session selector dropdown
- Sessions/Epics tab navigation
- View all stories with status
- Generate test scripts
- Collaborate: Update technical notes via prompts
- Approve/reject stories

---

### CLI Commands

```bash
# Submit new requirement (triggers requirement → epic → story)
python3 main.py new

# List all sessions
python3 main.py list

# View story details
python3 main.py view STORY-001

# Generate test scripts
python3 main.py tests STORY-001
python3 main.py tests --all

# Approve/reject stories
python3 main.py approve STORY-001
python3 main.py reject STORY-001

# Check pipeline status
python3 main.py status
```

---

## Configuration

### Agent Models (config/models.yaml)

Each agent can have its own model configuration:

```yaml
agents:
  requirement:
    model: meta-llama/llama-3.1-8b-instruct
    temperature: 0.3
    max_tokens: 4000

  epic:
    model: meta-llama/llama-3.1-8b-instruct
    temperature: 0.3
    max_tokens: 4000

  story:
    model: meta-llama/llama-3.1-8b-instruct
    temperature: 0.4
    max_tokens: 4000

  test_generator:
    model: meta-llama/llama-3.1-8b-instruct
    temperature: 0.2
    max_tokens: 3000

  collaborate:
    model: meta-llama/llama-3.1-8b-instruct
    temperature: 0.3
    max_tokens: 2000
```

---

## Project Structure

```
forward-agent/
├── agents/                    # Agent implementations
│   ├── requirement.py         # Requirement Agent
│   ├── epic.py               # Epic Agent
│   ├── story.py              # Story Agent
│   ├── test_generator.py     # Test Generator Agent
│   └── collaborate.py        # Collaborate Agent (LLM-powered)
├── core/                     # Core modules
│   ├── orchestrator.py       # Orchestration engine
│   ├── llm.py               # LLM client (OpenRouter)
│   ├── memory.py            # Session memory
│   ├── state.py             # Workflow state
│   └── tools.py             # Tool registry
├── config/                   # Configuration
│   ├── settings.py          # Settings loader
│   └── models.yaml          # Per-agent model config
├── web/                      # Web dashboard
│   ├── app.py               # Flask app
│   └── templates/            # HTML templates
│       ├── base.html        # Base template (TailwindCSS)
│       ├── dashboard.html   # Main dashboard
│       └── story.html       # Story detail + collaborate
├── artifacts/                # Generated outputs (runtime)
│   ├── requirements/
│   ├── epics/
│   ├── stories/
│   └── tests/
├── main.py                   # CLI entry point
├── requirements.txt          # Python dependencies
├── .env.example              # Environment template
└── README.md                 # This file
```

---

## Features

### Current Features
- ✅ Autonomous requirement → epic → story pipeline
- ✅ Web dashboard with session/epic/story navigation
- ✅ Human verification (approve/reject stories)
- ✅ LLM-powered collaborate feature for technical notes updates
- ✅ Per-agent model configuration via YAML
- ✅ Test script generation

### Future Features
- [ ] Code Agent implementation
- [ ] Figma MCP integration for mockups
- [ ] Auto-healing/debugging for production issues
- [ ] Git integration for code push
- [ ] Learn phase pattern recognition

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/dashboard` | GET | Dashboard UI |
| `/dashboard/story/<id>` | GET | Story detail UI |
| `/api/sessions` | GET | List all sessions |
| `/api/sessions/<id>/epics` | GET | Get epics with stories |
| `/api/sessions/<id>/stories` | GET | Get all stories |
| `/api/stories/<id>` | GET | Get story details |
| `/api/stories/<id>/tests` | POST | Generate test script |
| `/api/stories/<id>/approve` | POST | Approve story |
| `/api/stories/<id>/reject` | POST | Reject story |
| `/api/stories/<id>/collaborate` | POST | Update technical notes |
| `/api/stats` | GET | Pipeline statistics |

---

## Collaborate Feature

The collaborate feature implements the **ASD Collaborate phase**:

1. User clicks **Collaborate** button on story detail page
2. Modal shows current `technical_notes` as context
3. User enters requirement change (technical or non-technical)
4. LLM analyzes prompt + current notes → intelligently updates notes
5. Changes can be: append, modify, remove, or restructure

**Example:**
- User: `Change login to Google OAuth2`
- AI: Updates technical_notes to include OAuth2 requirement
- User: `Add tips button at input box`
- AI: Appends new UI requirement to technical notes