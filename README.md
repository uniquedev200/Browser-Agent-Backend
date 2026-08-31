# BrowserAuto Backend

Server-side backend for a privacy-preserving browser automation agent. The backend receives sanitized browser state and screenshots, reasons over them using a local VLM, and returns structured browser action plans. **No raw PII ever reaches the server.**

## Architecture

```
                  +----------------------+
                  |   Browser Extension  |
                  +----------+-----------+
                             |
                   session_id + task
                   sanitized screenshot
                   browser_state
                   execution_results
                             |
                             v
                     +-------------+
                     |   FastAPI   |
                     +------+------+
                            |
                            v
                   +----------------+
                   | Session Manager|
                   +-------+--------+
                           |
                           v
                   +----------------+
                   |Workflow Manager|
                   +-------+--------+
                           |
                           v
                +-----------------------+
                | Browser State         |
                | Validator             |
                +----------+------------+
                           |
                           v
                    +--------------+
                    |Prompt Builder|
                    +------+-------+
                           |
                           v
                 +--------------------+
                 | VLM Engine         |
                 | (llama.cpp / HF)   |
                 +---------+----------+
                           |
                           v
                  +------------------+
                  | Action Validator |
                  +--------+---------+
                           |
                           v
                  Structured Action
                         JSON
                           |
                           v
                   Browser Extension
                           |
                           v
                    Execute Actions
                           |
                           v
                  Capture New State
                           |
                           +----------> repeat
```

## Tech Stack

- **Runtime**: Python 3.13, FastAPI, Pydantic v2, Uvicorn
- **VLM (primary)**: llama.cpp + GGUF model via OpenAI-compatible API
  - Model: `Qwen2.5-VL-3B-Instruct` (Q4_K_M quantized, ~2.3GB)
  - Projector: `mmproj-Qwen2.5-VL-3B-Instruct` (Q8_0, ~554MB)
  - Server: llama-server from Docker Desktop (`C:\Users\suraj\.docker\bin\inference\llama-server.exe`)
  - Backend: Vulkan (RTX 3050 6GB)
- **VLM (fallback)**: HuggingFace Transformers + BitsAndBytes (NF4 quantization)
- **Database**: Supabase PostgreSQL via asyncpg (direct connection)
- **GPU**: NVIDIA RTX 3050 6GB Laptop, driver 581.86

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/uniquedev200/Browser-Agent-Backend.git
cd browserauto_backend
```

### 2. Create a virtual environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
copy .env.example .env
```

Edit `.env` with your settings:

```text
# VLM Backend: "llamacpp" (default) or "hf"
VLM_BACKEND=llamacpp

# llama.cpp settings
LLAMACPP_URL=http://127.0.0.1:8081
GGUF_MODEL_PATH=C:\Models\Qwen2.5-VL-3B-GGUF\Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf
MMProj_PATH=C:\Models\Qwen2.5-VL-3B-GGUF\mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf

# HuggingFace fallback settings
MODEL_PATH=C:\Users\suraj\Qwen2-VL-2B

# Server settings
HOST=127.0.0.1
PORT=8000
MAX_NEW_TOKENS=512
MAX_IMAGE_WIDTH=640
MAX_IMAGE_HEIGHT=640

# Storage
STORAGE_BACKEND=pg
DATABASE_URL=postgresql://postgres.tanyuidzfgeqnghwzywt:<YOUR-PASSWORD>@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres

# Other
MAX_RETRIES=3
SESSION_TTL_SECONDS=3600
LOG_LEVEL=INFO
DEBUG_TIMINGS=true
```

### 5. Start llama-server (if using llama.cpp backend)

```bash
# From Docker Desktop's bundled llama.cpp
C:\Users\suraj\.docker\bin\inference\llama-server.exe ^
  --model C:\Models\Qwen2.5-VL-3B-GGUF\Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf ^
  --mmproj C:\Models\Qwen2.5-VL-3B-GGUF\mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf ^
  --host 127.0.0.1 --port 8081 -ngl 99 -c 4096
```

Wait ~15 seconds for model to load.

### 6. Start the backend

```bash
python -m backend.main
```

The server starts on `http://127.0.0.1:8000`.

### 7. Verify

```bash
curl http://127.0.0.1:8000/health
```

Response: `{"status": "ok"}`

## Performance

| Metric | llama.cpp (Q4_K_M) | HuggingFace (NF4) |
|--------|--------------------|--------------------|
| VLM inference | **3.2-4.3s** | ~15s |
| Total latency | **4.6-5.6s** | ~17s |
| Model size | ~2.3GB | ~2.3GB |
| VRAM usage | ~3GB | ~3.5GB |
| GPU backend | Vulkan | CUDA |
| Dependencies | llama-server only | torch + transformers + bitsandbytes |

## API Endpoints

### Health Check

```http
GET /health
```

### Create Session

```http
POST /api/v1/session
Content-Type: application/json

{
  "session_id": "sess_abc123",
  "task": "Complete the internship application"
}
```

### Get Session

```http
GET /api/v1/session/{session_id}
```

### Delete Session

```http
DELETE /api/v1/session/{session_id}
```

### Infer (Main Agent Endpoint)

```http
POST /api/v1/infer
Content-Type: application/json

{
  "session_id": "sess_001",
  "task": "Complete the registration form",
  "browser_state": {
    "page": {
      "title": "Registration",
      "url": "https://example.com/register",
      "viewport": {"width": 1440, "height": 900},
      "scroll": {"x": 0, "y": 0}
    },
    "elements": [
      {
        "element_id": "name_1",
        "role": "textbox",
        "label": "Full Name",
        "value": "",
        "bbox": [100, 150, 300, 40],
        "visible": true,
        "enabled": true
      },
      {
        "element_id": "email_1",
        "role": "textbox",
        "type": "email",
        "label": "Email",
        "value": "",
        "bbox": [100, 220, 300, 40],
        "visible": true,
        "enabled": true
      },
      {
        "element_id": "submit_1",
        "role": "button",
        "text": "Submit",
        "bbox": [100, 300, 120, 40],
        "visible": true,
        "enabled": true
      }
    ]
  },
  "screenshot": {
    "mime_type": "image/png",
    "data": "<BASE64_SANITIZED_IMAGE>"
  },
  "execution_results": []
}
```

Response:

```json
{
  "session_id": "sess_001",
  "status": "continue",
  "actions": [
    {
      "action_id": "a1",
      "type": "fill",
      "target": "name_1",
      "value": "<PERSON>"
    },
    {
      "action_id": "a2",
      "type": "fill",
      "target": "email_1",
      "value": "<EMAIL>"
    },
    {
      "action_id": "a3",
      "type": "click",
      "target": "submit_1"
    }
  ],
  "checkpoint": true,
  "reason": "All visible form fields can be filled and submitted",
  "timings": {
    "vlm_ms": 3200.0,
    "total_ms": 3500.0
  }
}
```

## Browser State Schema

```python
class BrowserState:
    page: PageMetadata
    elements: list[ElementState]

class PageMetadata:
    title: str
    url: str
    domain: str
    viewport: Viewport      # {width, height}
    scroll: ScrollPosition  # {x, y}

class ElementState:
    element_id: str          # required
    role: str                # textbox, button, combobox, checkbox
    type: str                # email, text, tel, etc.
    tag: str                 # optional
    text: str                # visible text
    label: str               # label
    placeholder: str
    value: str               # may contain <EMAIL>, <PHONE>, etc.
    bbox: list[int]          # [x, y, width, height]
    visible: bool
    enabled: bool
    focused: bool
    checked: bool | None
    expanded: bool | None
    selected: bool | None
    disabled: bool | None
```

## Action Schema

```python
class Action:
    action_id: str           # required, unique
    type: str                # required, one of supported types
    target: str | None       # element_id to act on
    value: str | None        # fill value, placeholder
    key: str | None          # for press_key
    direction: str | None    # for scroll: up/down/left/right
    amount: int | None       # for scroll: pixels
    selector: str | None     # optional CSS selector
```

Supported action types: `click`, `fill`, `select`, `check`, `uncheck`, `scroll`, `wait`, `press_key`, `upload`, `done`

## Session Lifecycle

1. Client sends first request with a `session_id`
2. Server creates a new session automatically
3. Server validates previous execution (if any)
4. Server updates workflow state
5. Server builds prompt from session state + browser state
6. VLM generates structured action JSON
7. Action Validator filters invalid actions
8. Server returns valid actions to client
9. Client executes actions locally, captures new state
10. Client sends next request with same `session_id`
11. Repeat until status is `done`

## Smart Prompt System

The prompt builder dynamically adapts to the current state:

- **Pending elements**: Only shows elements that need action (empty textboxes, unchecked checkboxes)
- **Completed elements**: Shows already-filled elements separately
- **Dynamic example**: Generates a concrete example using actual element_ids
- **Done detection**: Returns `status: "done"` when all elements are completed

This ensures the VLM only generates actions for elements that actually need them.

## Multi-user Architecture

One VLM instance serves multiple browser sessions concurrently. Session state is isolated by `session_id`. No mutable per-user state is stored in process-global variables. The PostgreSQL database (or in-memory store) is the source of truth.

```
VLM (shared)
     |
     +---- Session A (sess_001)
     |
     +---- Session B (sess_002)
     |
     +---- Session C (sess_003)
```

## Security & Privacy

- **No raw PII**: The server only sees `<EMAIL>`, `<PHONE>`, `<PERSON>`, etc.
- **Sanitized screenshots only**: Client strips PII from images before sending
- **No reverse engineering**: Server never attempts to resolve placeholders to real values
- **Prompt injection defense**: System prompt explicitly treats webpage text as data, not instructions
- **No secrets in logs**: Logging omits screenshots, PII, full request bodies
- **Action validation**: Unknown actions, shell commands, and JavaScript injection are rejected
- **Session isolation**: Different users' states never overlap
- **Placeholder validation**: Only `<EMAIL>`, `<PHONE>`, `<PERSON>`, etc. are allowed as values

## Placeholder Values

The server works with semantic placeholders only:

| Placeholder | Meaning |
|-------------|---------|
| `<EMAIL>` | User's email address |
| `<PHONE>` | User's phone number |
| `<PASSWORD>` | User's password |
| `<PERSON>` | User's name |
| `<CREDIT_CARD>` | Credit card number |
| `<ACCOUNT_NUMBER>` | Account number |
| `<ADDRESS>` | Physical address |
| `<OTP>` | One-time password |

The client resolves placeholders using its local Secure User Vault. The server never sees actual values.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `VLM_BACKEND` | `llamacpp` | `llamacpp` or `hf` |
| `LLAMACPP_URL` | `http://127.0.0.1:8081` | llama-server API URL |
| `GGUF_MODEL_PATH` | (set in .env) | Path to GGUF model file |
| `MMProj_PATH` | (set in .env) | Path to mmproj file |
| `MODEL_PATH` | `C:\Users\suraj\Qwen2-VL-2B` | HF model path (fallback) |
| `HOST` | `127.0.0.1` | Server host |
| `PORT` | `8000` | Server port |
| `MAX_NEW_TOKENS` | `512` | Max VLM generation tokens |
| `MAX_IMAGE_WIDTH` | `640` | Max image width for VLM |
| `MAX_IMAGE_HEIGHT` | `640` | Max image height for VLM |
| `MAX_RETRIES` | `3` | Max retry count before blocking |
| `SESSION_TTL_SECONDS` | `3600` | Session TTL |
| `LOG_LEVEL` | `INFO` | Logging level |
| `STORAGE_BACKEND` | `pg` | `memory` or `pg` |
| `DATABASE_URL` | (empty) | Supabase PostgreSQL connection string |
| `DEBUG_TIMINGS` | `false` | Include timing data in responses |

## Troubleshooting

### llama-server fails to start

- Ensure `llama-server.exe` exists at `C:\Users\suraj\.docker\bin\inference\`
- Check that GGUF model files exist at `C:\Models\Qwen2.5-VL-3B-GGUF\`
- Verify Vulkan is available: `vulkaninfo --summary`
- Check GPU VRAM: model requires ~3GB

### Backend can't connect to llama-server

- Ensure llama-server is running on port 8081
- Check `LLAMACPP_URL` in `.env` matches llama-server's host/port
- Try: `curl http://127.0.0.1:8081/v1/models`

### HuggingFace backend issues

- Set `VLM_BACKEND=hf` in `.env`
- Verify CUDA: `python -c "import torch; print(torch.cuda.is_available())"`
- Check GPU VRAM: requires ~3.5GB with NF4 quantization

### PostgreSQL connection fails

- Verify `DATABASE_URL` is correct
- Check network connectivity to Supabase
- Ensure `asyncpg` is installed
- Falls back to in-memory storage automatically

### Tests fail

```bash
pip install pytest pytest-asyncio
pytest backend/tests/ -v
```

## Test Commands

```bash
# Run all tests
pytest backend/tests/ -v

# Run specific test files
pytest backend/tests/test_session.py -v
pytest backend/tests/test_workflow.py -v
pytest backend/tests/test_validation.py -v
pytest backend/tests/test_actions.py -v
pytest backend/tests/test_api.py -v

# Run full end-to-end test (starts servers + infer)
python scripts/test_full.py

# Run multi-turn loop test
python scripts/test_loop.py
```

## Project Structure

```
backend/
|
+-- main.py                    # FastAPI app, lifespan, startup
+-- config/
|   +-- settings.py            # Environment configuration
+-- api/
|   +-- routes.py              # API endpoints
+-- schemas/
|   +-- request.py             # Request/response models
|   +-- browser_state.py       # Browser state schema
|   +-- action.py              # Action and action batch schema
|   +-- session.py             # Session data schema
+-- session/
|   +-- session_manager.py     # Session CRUD operations
+-- workflow/
|   +-- workflow_manager.py    # Deterministic workflow state machine
+-- validation/
|   +-- browser_state_validator.py  # State transition validation
+-- prompts/
|   +-- prompt_builder.py      # Dynamic prompt assembly
+-- vlm/
|   +-- llamacpp_engine.py     # llama.cpp engine (primary)
|   +-- qwen_engine.py         # HuggingFace engine (fallback)
+-- actions/
|   +-- action_validator.py    # Action safety + fuzzy target matching
+-- storage/
|   +-- base.py                # Storage abstraction
|   +-- memory_store.py        # In-memory store
|   +-- pg_store.py            # PostgreSQL store
+-- utils/
|   +-- hashing.py             # Browser state hashing
|   +-- logging.py             # Safe logging utilities
+-- tests/
    +-- conftest.py            # Test configuration
    +-- fixtures.py            # Synthetic test data
    +-- test_session.py        # Session manager tests
    +-- test_workflow.py       # Workflow manager tests
    +-- test_validation.py     # State validation tests
    +-- test_actions.py        # Action validation tests
    +-- test_api.py            # API endpoint tests

scripts/
+-- test_full.py               # Full end-to-end test
+-- test_loop.py               # Multi-turn loop test
+-- check_elements.py          # Debug element inspection
```
