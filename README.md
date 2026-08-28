# BrowserAuto Backend

Server-side backend for a privacy-preserving browser automation agent. The backend receives sanitized browser state and screenshots, reasons over them using a local Qwen2.5-VL-3B model, and returns structured browser action plans. **No raw PII ever reaches the server.**

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
                 | Qwen2.5-VL-3B     |
                 | Local Open-Weight  |
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

- Python 3.11
- FastAPI + Uvicorn
- Pydantic v2
- PyTorch + Transformers (Qwen2.5-VL)
- BitsAndBytes (4-bit NF4 quantization)
- asyncpg (Supabase PostgreSQL direct connection)
- PIL/Pillow for image processing

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
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

Edit `.env` with your settings. Key variables:

```text
MODEL_PATH=C:\Users\suraj\Qwen2.5-VL-3B
HOST=127.0.0.1
PORT=8000
MAX_NEW_TOKENS=512
MAX_RETRIES=3
SESSION_TTL_SECONDS=3600
LOG_LEVEL=INFO
STORAGE_BACKEND=memory
DEBUG_TIMINGS=true
```

For PostgreSQL storage, set:

```text
DATABASE_URL=postgresql://postgres.tanyuidzfgeqnghwzywt:<YOUR-PASSWORD>@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
STORAGE_BACKEND=pg
```

### 5. Start the server

```bash
python -m backend.main
```

The server starts on `http://127.0.0.1:8000`.

### 6. Verify

```bash
curl http://127.0.0.1:8000/health
```

Response: `{"status": "ok"}`

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
    }
  ],
  "checkpoint": true,
  "reason": "Both visible registration fields can be filled safely.",
  "timings": {
    "session_ms": 2.1,
    "validation_ms": 0.5,
    "prompt_ms": 0.3,
    "vlm_ms": 812.4,
    "validation_output_ms": 0.2,
    "total_ms": 815.5
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
    role: str                # textbox, button, combobox, etc.
    type: str                # email, text, tel, checkbox, etc.
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
6. Qwen2.5-VL generates structured action JSON
7. Action Validator filters invalid actions
8. Server returns valid actions to client
9. Client executes actions locally, captures new state
10. Client sends next request with same `session_id`
11. Repeat until status is `done`

## Multi-user Architecture

One Qwen model instance serves multiple browser sessions concurrently. Session state is isolated by `session_id`. No mutable per-user state is stored in process-global variables. The PostgreSQL database (or in-memory store) is the source of truth.

```
Qwen Model (shared)
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
| `MODEL_PATH` | `C:\Users\suraj\Qwen2.5-VL-3B` | Local model path |
| `HOST` | `127.0.0.1` | Server host |
| `PORT` | `8000` | Server port |
| `MAX_NEW_TOKENS` | `512` | Max VLM generation tokens |
| `MAX_RETRIES` | `3` | Max retry count before blocking |
| `SESSION_TTL_SECONDS` | `3600` | Session TTL |
| `LOG_LEVEL` | `INFO` | Logging level |
| `STORAGE_BACKEND` | `memory` | `memory` or `pg` |
| `DATABASE_URL` | (empty) | Supabase PostgreSQL connection string |
| `DEBUG_TIMINGS` | `false` | Include timing data in responses |

## Troubleshooting

### Model fails to load

- Ensure the model path `C:\Users\suraj\Qwen2.5-VL-3B` exists and contains model files
- Verify CUDA is available: `python -c "import torch; print(torch.cuda.is_available())"`
- Check GPU VRAM: the model requires ~3GB with 4-bit quantization
- Ensure `bitsandbytes` is installed and working with CUDA

### GPU out of memory

- Close other GPU-intensive applications
- Reduce `MAX_NEW_TOKENS` in `.env`
- Verify 4-bit quantization is enabled (NF4 config)

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

# Run specific test file
pytest backend/tests/test_session.py -v
pytest backend/tests/test_workflow.py -v
pytest backend/tests/test_validation.py -v
pytest backend/tests/test_actions.py -v
pytest backend/tests/test_api.py -v
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
|   +-- prompt_builder.py      # Deterministic prompt assembly
+-- vlm/
|   +-- qwen_engine.py         # Qwen2.5-VL model wrapper
+-- actions/
|   +-- action_validator.py    # Action safety validation
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
```
