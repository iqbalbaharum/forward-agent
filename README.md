# Forward Agent - Agile AI Multi-Agent System

An AI-powered system that transforms requirements into epics, user stories, and test scripts using the Forward development methodology.

## Architecture

```
User Input (Requirement)
         │
         ▼ (autonomous)
┌─────────────────┐
│ Requirement     │
│ Agent           │
└─────────────────┘
         ▼ (autonomous)
┌─────────────────┐
│ Epic Agent      │
│                 │
└─────────────────┘
         ▼ (autonomous)
┌─────────────────┐
│ Story Agent     │
│                 │
└─────────────────┘
         ▼ (user verifies)
┌─────────────────┐
│ Human Verify    │ ◄─── User reviews stories + test scripts
│ (Stories+Tests) │
└─────────────────┘
```

## Requirements

- Python 3.10+
- Qwen API key (Alibaba Cloud)

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env and add your QWEN_API_KEY
   ```

3. **Get Qwen API key:**
   - Sign up at [Alibaba Cloud Model Studio](https://modelstudio.console.alibabacloud.com/)
   - Create API key and add to `.env`

## Usage

### Submit a new requirement
```bash
python main.py new "Build a user authentication system with login, registration, and password reset"
```

### List all sessions
```bash
python main.py list
```

### View story details
```bash
python main.py view STORY-001
```

### Generate test scripts
```bash
python main.py tests STORY-001
# or generate for all pending stories:
python main.py tests --all
```

### Approve/reject stories
```bash
python main.py approve STORY-001
python main.py reject STORY-001 "Missing acceptance criteria for password validation"
```

### Check pipeline status
```bash
python main.py status
```

## Project Structure

```
forward-agent/
├── agents/              # Agent implementations
│   ├── requirement.py   # Requirement Agent
│   ├── epic.py          # Epic Agent
│   ├── story.py         # Story Agent
│   └── test_generator.py # Test Generator Agent
├── core/                # Core modules
│   ├── orchestrator.py  # Orchestration engine
│   ├── llm.py          # LLM client (Qwen)
│   ├── memory.py       # Session memory
│   ├── state.py        # Workflow state
│   └── tools.py        # Tool registry
├── config/             # Configuration
│   └── settings.py
├── artifacts/          # Generated outputs (runtime)
│   ├── requirements/
│   ├── epics/
│   ├── stories/
│   └── tests/
└── main.py            # CLI entry point
```

## Future Features

- [ ] Code Agent implementation
- [ ] Auto-healing/debugging for production issues
- [ ] Git integration for code push
- [ ] More LLM provider options