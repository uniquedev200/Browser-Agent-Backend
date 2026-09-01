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

## API Reference

**Base URL:** `http://127.0.0.1:8000`

All endpoints accept and return JSON. Content-Type: `application/json`.

---

### `GET /health`

Check if the server is running.

**Response:**
```json
{"status": "ok"}
```

---

### `POST /api/v1/session`

Create a new session or resume an existing one.

**Request:**
```json
{
  "session_id": "sess_001",
  "task": "Fill the internship application form"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | yes | Unique ID for this browser session |
| `task` | string | no | What the agent should do |

**Response:**
```json
{
  "session_id": "sess_001",
  "status": "RUNNING",
  "created_at": "2026-09-01T12:00:00+00:00"
}
```

---

### `GET /api/v1/session/{session_id}`

Get current session state.

**Response:**
```json
{
  "session_id": "sess_001",
  "task": "Fill the internship application form",
  "status": "RUNNING",
  "phase": "fill",
  "step_index": 2,
  "retry_count": 0,
  "created_at": "2026-09-01T12:00:00+00:00",
  "updated_at": "2026-09-01T12:00:15+00:00"
}
```

---

### `DELETE /api/v1/session/{session_id}`

Delete a session and all its data.

**Response:**
```json
{"status": "deleted", "session_id": "sess_001"}
```

---

### `POST /api/v1/infer` (Main Endpoint)

Send browser state + screenshot, get back actions to execute.

**Full Request Example:**
```json
{
  "session_id": "sess_001",
  "task": "Fill the internship application form",
  "browser_state": {
    "page": {
      "title": "Software Engineer Internship",
      "url": "https://example.com/apply",
      "viewport": {"width": 1440, "height": 900},
      "scroll": {"x": 0, "y": 0}
    },
    "elements": [
      {
        "element_id": "name",
        "role": "textbox",
        "label": "Full Name",
        "value": "",
        "bbox": [70, 184, 760, 45],
        "visible": true,
        "enabled": true
      },
      {
        "element_id": "email",
        "role": "textbox",
        "label": "Email Address",
        "value": "",
        "bbox": [70, 268, 760, 45],
        "visible": true,
        "enabled": true
      },
      {
        "element_id": "terms",
        "role": "checkbox",
        "label": "I agree to the terms",
        "checked": false,
        "bbox": [70, 520, 18, 18],
        "visible": true,
        "enabled": true
      },
      {
        "element_id": "submit",
        "role": "button",
        "text": "Submit",
        "bbox": [70, 592, 120, 44],
        "visible": true,
        "enabled": true
      }
    ]
  },
  "screenshot": {
    "mime_type": "image/png",
    "data": "iVBORw0KGgoAAAANS..."
  },
  "available_keys": ["FullName", "Email", "Phone", "Address"],
  "execution_results": []
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | yes | Same session_id from create |
| `task` | string | no | Task description (sent to VLM) |
| `browser_state` | object | yes | Current page state with ALL elements |
| `screenshot` | object | no | Base64-encoded sanitized screenshot |
| `available_keys` | object | no | Encrypted key-value pairs from client vault |
| `execution_results` | array | no | Results from previous action batch |

**Important about `browser_state`:**
- Send ALL elements on the page, not just visible ones
- Include `viewport` width/height and `scroll` x/y
- Backend uses these to detect which elements are visible vs off-screen
- `bbox` format: `[x, y, width, height]`

**Important about `available_keys`:**
- Send only the **key names** from your local vault (e.g., "FullName", "Email", "Phone")
- Never send encrypted values to the server
- Server returns `key` field in fill actions, you decrypt locally using your vault

**Response (Turn 1 - visible fields):**
```json
{
  "session_id": "sess_001",
  "status": "continue",
  "actions": [
    {"action_id": "a0", "type": "scroll", "direction": "down"},
    {"action_id": "a1", "type": "fill", "target": "name", "key": "FullName"},
    {"action_id": "a2", "type": "fill", "target": "email", "key": "Email"}
  ],
  "checkpoint": true,
  "reason": "Filling visible form fields"
}
```

**Response (Turn 2 - after scrolling):**
```json
{
  "session_id": "sess_001",
  "status": "continue",
  "actions": [
    {"action_id": "a1", "type": "check", "target": "terms"},
    {"action_id": "a2", "type": "click", "target": "submit"}
  ],
  "checkpoint": true,
  "reason": "Checking terms and submitting"
}
```

**Response (Form submitted):**
```json
{
  "session_id": "sess_001",
  "status": "done",
  "actions": [],
  "checkpoint": true,
  "reason": "Page navigated: https://example.com/apply -> https://example.com/thank-you"
}
```

| Response Field | Type | Description |
|----------------|------|-------------|
| `status` | string | `"continue"` = send next batch, `"done"` = task complete, `"blocked"` = error |
| `actions` | array | List of actions to execute locally |
| `checkpoint` | bool | `true` = capture new state after executing |
| `reason` | string | VLM's reasoning |
| `timings` | object | Only when `DEBUG_TIMINGS=true` |

---

## Action Types

### `fill` - Fill a textbox
```json
{"action_id": "a1", "type": "fill", "target": "name", "key": "FullName"}
```
- `target`: element_id of the textbox
- `key`: key from `available_keys` to use (you decrypt locally)

### `check` - Check a checkbox
```json
{"action_id": "a2", "type": "check", "target": "terms"}
```

### `click` - Click a button
```json
{"action_id": "a3", "type": "click", "target": "submit"}
```

### `scroll` - Scroll to reveal off-screen elements
```json
{"action_id": "a0", "type": "scroll", "direction": "down"}
```
- `direction`: `"down"`, `"up"`, `"left"`, `"right"`

### `done` - Task completed
```json
{"action_id": "a1", "type": "done"}
```

---

## Frontend Integration Flow

```
1. Create session
   POST /api/v1/session {session_id, task}

2. Capture browser state + screenshot
   - Get ALL elements (visible + off-screen)
   - Get viewport size and scroll position
   - Sanitize screenshot (strip PII from images)

3. Send to backend
   POST /api/v1/infer {session_id, browser_state, screenshot, available_keys}

4. Execute actions locally
   - For fill: look up key in local vault, decrypt, fill field
   - For check: toggle checkbox
   - For click: click button
   - For scroll: scroll page

5. Capture new state (if checkpoint=true)

6. Send execution results with next request
   POST /api/v1/infer {session_id, browser_state, screenshot, execution_results: [{action_id, status}]}

7. Repeat until status="done"
```

**Example execution_results:**
```json
{
  "execution_results": [
    {"action_id": "a0", "status": "ok"},
    {"action_id": "a1", "status": "ok"},
    {"action_id": "a2", "status": "ok"}
  ]
}
```

---

## Loop Termination

The backend automatically terminates when:

| Condition | Example |
|-----------|---------|
| **Success message in DOM** | Page contains "submitted", "thank you", "success" |
| **Page navigation** | URL changed after click action |
| **All fields filled** | Every textbox has value, every checkbox is checked |
| **Loop detected** | Same browser state sent 3+ times |
| **Max retries** | 3+ failed validation attempts |

When terminated, response has `"status": "done"` and empty `actions` array.

---

## Browser State Schema

```typescript
interface BrowserState {
  page: {
    title: string;          // Page title
    url: string;            // Full URL
    viewport: { width: number; height: number };
    scroll: { x: number; y: number };
  };
  elements: ElementState[];
}

interface ElementState {
  element_id: string;       // REQUIRED - unique identifier
  role: string;             // "textbox" | "button" | "checkbox" | "combobox"
  type?: string;            // "email" | "text" | "tel" | "password" | etc.
  tag?: string;             // "input" | "button" | "select" | etc.
  text?: string;            // Visible text content
  label?: string;           // Label text
  placeholder?: string;     // Placeholder text
  value?: string;           // Current value (empty = needs fill)
  bbox: number[];           // [x, y, width, height] - REQUIRED
  visible: boolean;         // REQUIRED
  enabled: boolean;         // REQUIRED
  checked?: boolean;        // For checkboxes
  selected?: boolean;       // For dropdowns
}
```

**Critical:** Always send ALL elements, even off-screen ones. Backend uses `bbox` + `viewport` + `scroll` to determine visibility.

## Session Lifecycle

1. Client creates session with `session_id` + `task`
2. Client sends browser state + screenshot + available_keys
3. Backend splits elements by visibility (viewport + scroll)
4. Backend builds prompt with visible/off-screen sections
5. VLM generates actions (scroll + fill + check + click)
6. Backend validates actions against available_keys
7. Backend returns actions to client
8. Client executes actions locally:
   - For `fill`: decrypt key from local vault, fill field
   - For `check`: toggle checkbox
   - For `click`: click button
   - For `scroll`: scroll page
9. Client captures new state, sends next request
10. Backend checks for completion (page nav, success message, all filled)
11. Repeat until `status="done"`

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

- **Key-based fills**: Server only sees encrypted keys (e.g., "FullName"), never actual values
- **Local vault**: Client decrypts keys locally - PII never leaves the device
- **Sanitized screenshots**: Client strips PII from images before sending
- **No reverse engineering**: Server never attempts to resolve keys to actual values
- **Prompt injection defense**: System prompt treats webpage text as data, not instructions
- **No secrets in logs**: Logging omits screenshots, keys, full request bodies
- **Action validation**: Unknown actions, shell commands, and JavaScript injection are rejected
- **Session isolation**: Different users' states never overlap

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
