# BrowserAuto Backend API Documentation

Base URL: `http://127.0.0.1:8000`

Interactive docs are also available at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## Endpoints

### 1. Health Check

```
GET /health
```

Check if the server is running.

**Response** `200 OK`

```json
{
  "status": "ok"
}
```

---

### 2. Create Session

```
POST /api/v1/session
Content-Type: application/json
```

Create or resume a session. If the session_id already exists, returns the existing session.

**Request Body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | yes | Unique session identifier (e.g. `sess_abc123`) |
| `task` | string | no | The user's task/goal |

**Example**

```json
{
  "session_id": "sess_001",
  "task": "Complete the internship application"
}
```

**Response** `200 OK`

```json
{
  "session_id": "sess_001",
  "status": "RUNNING",
  "created_at": "2026-08-27T13:45:37.231094+00:00"
}
```

---

### 3. Get Session

```
GET /api/v1/session/{session_id}
```

Retrieve sanitized session state for debugging. Does not expose raw PII or full browser state.

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `session_id` | string | The session to retrieve |

**Response** `200 OK`

```json
{
  "session_id": "sess_001",
  "task": "Complete the internship application",
  "status": "RUNNING",
  "phase": "fill_form",
  "summary": "Filling out the form fields with placeholders.",
  "step_index": 3,
  "retry_count": 0,
  "created_at": "2026-08-27T13:45:37.231094+00:00",
  "updated_at": "2026-08-27T13:46:50.579538+00:00"
}
```

**Response** `404 Not Found`

```json
{
  "detail": "Session not found"
}
```

---

### 4. Delete Session

```
DELETE /api/v1/session/{session_id}
```

Delete a session and all associated data (cascade).

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `session_id` | string | The session to delete |

**Response** `200 OK`

```json
{
  "status": "deleted",
  "session_id": "sess_001"
}
```

**Response** `404 Not Found`

```json
{
  "detail": "Session not found"
}
```

---

### 5. Infer (Main Agent Endpoint)

```
POST /api/v1/infer
Content-Type: application/json
```

The core endpoint. Sends the current browser state + screenshot to the VLM and receives structured action instructions.

**Request Body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | yes | Session to continue or create |
| `task` | string | no | User's task goal (used on first request) |
| `browser_state` | object | yes | Normalized browser state (see schema below) |
| `screenshot` | object | no | Sanitized screenshot (`{mime_type, data}`) |
| `execution_results` | array | no | Results from previous action batch |

**Screenshot Object**

| Field | Type | Description |
|-------|------|-------------|
| `mime_type` | string | Image MIME type (e.g. `image/png`) |
| `data` | string | Base64-encoded sanitized image |

**Example Request**

```json
{
  "session_id": "sess_001",
  "task": "Complete the Software Engineer Internship application form",
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
        "type": "text",
        "label": "Full Name",
        "value": "<PERSON>",
        "bbox": [70, 184, 760, 45],
        "visible": true,
        "enabled": true
      },
      {
        "element_id": "email",
        "role": "textbox",
        "type": "email",
        "label": "Email Address",
        "value": "<EMAIL>",
        "bbox": [70, 268, 760, 45],
        "visible": true,
        "enabled": true
      },
      {
        "element_id": "next",
        "role": "button",
        "text": "Next",
        "bbox": [204, 592, 96, 44],
        "visible": true,
        "enabled": true
      }
    ]
  },
  "screenshot": {
    "mime_type": "image/png",
    "data": "<BASE64_ENCODED_IMAGE>"
  },
  "execution_results": []
}
```

**Response** `200 OK`

```json
{
  "session_id": "sess_001",
  "status": "continue",
  "actions": [
    {
      "action_id": "name",
      "type": "fill",
      "target": "name",
      "value": "<PERSON>"
    },
    {
      "action_id": "email",
      "type": "fill",
      "target": "email",
      "value": "<EMAIL>"
    }
  ],
  "checkpoint": true,
  "reason": "Filling out the form fields with placeholders.",
  "timings": {
    "session_ms": 1.7,
    "validation_ms": 0.004,
    "workflow_ms": 0.45,
    "prompt_ms": 0.41,
    "vlm_ms": 72425.4,
    "validation_output_ms": 4.1,
    "total_ms": 74922.0
  }
}
```

**Response Fields**

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session identifier |
| `status` | string | `continue`, `done`, `blocked`, or `error` |
| `actions` | array | List of actions for the browser to execute |
| `checkpoint` | boolean | Whether the client should capture a new state after executing |
| `reason` | string | VLM's reasoning for the action batch |
| `timings` | object | Timing breakdown (only when `DEBUG_TIMINGS=true`) |

**Status Values**

| Status | Meaning |
|--------|---------|
| `continue` | Execute the actions and send back the new state |
| `done` | Task is complete, no more actions needed |
| `blocked` | Agent is stuck (repeated failures, loop detected) |
| `error` | Server-side error (VLM failure, etc.) |

---

## Action Schema

Each action in the `actions` array has:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action_id` | string | yes | Unique identifier for this action |
| `type` | string | yes | Action type (see below) |
| `target` | string | no | `element_id` to act on |
| `value` | string | no | Value for fill/select actions |
| `key` | string | no | Key name for `press_key` |
| `direction` | string | no | `up`/`down`/`left`/`right` for scroll |
| `amount` | integer | no | Pixel amount for scroll |

**Supported Action Types**

| Type | Description | Requires `target` | Requires `value` |
|------|-------------|-------------------|------------------|
| `click` | Click an element | yes | no |
| `fill` | Fill a text field | yes | yes |
| `select` | Select a dropdown option | yes | yes |
| `check` | Check a checkbox | yes | no |
| `uncheck` | Uncheck a checkbox | yes | no |
| `scroll` | Scroll the page | no | no |
| `wait` | Wait briefly | no | no |
| `press_key` | Press a keyboard key | no | no (`key` required) |
| `upload` | Upload a file | yes | yes |
| `done` | Task complete | no | no |

**Page-Terminating Actions**

After these actions, the client must capture a new browser state before sending the next request:
- `click` (on submit/next buttons)
- `scroll`
- `upload`

---

## Browser State Schema

```json
{
  "page": {
    "title": "Page Title",
    "url": "https://example.com/page",
    "domain": "example.com",
    "viewport": {"width": 1440, "height": 900},
    "scroll": {"x": 0, "y": 0}
  },
  "elements": [
    {
      "element_id": "unique_id",
      "role": "textbox",
      "type": "email",
      "tag": "input",
      "text": "Visible text",
      "label": "Field label",
      "placeholder": "Placeholder text",
      "value": "<EMAIL>",
      "bbox": [x, y, width, height],
      "visible": true,
      "enabled": true,
      "focused": false,
      "checked": false,
      "expanded": null,
      "selected": null,
      "disabled": null
    }
  ]
}
```

**Element Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `element_id` | string | yes | Unique identifier |
| `role` | string | no | ARIA role: `textbox`, `button`, `checkbox`, `combobox`, `heading`, `paragraph`, `status`, etc. |
| `type` | string | no | Input type: `text`, `email`, `tel`, `password`, `checkbox`, etc. |
| `tag` | string | no | HTML tag name |
| `text` | string | no | Visible text content |
| `label` | string | no | Label text |
| `placeholder` | string | no | Placeholder text |
| `value` | string | no | Current value (may contain semantic placeholders) |
| `bbox` | array | no | Bounding box: `[x, y, width, height]` |
| `visible` | boolean | no | Whether element is visible |
| `enabled` | boolean | no | Whether element is interactable |
| `focused` | boolean | no | Whether element has focus |
| `checked` | boolean | no | Checkbox state |
| `expanded` | boolean | no | Expandable state |
| `selected` | boolean | no | Selection state |
| `disabled` | boolean | no | Disabled state |

---

## Semantic Placeholders

The server only works with privacy-safe placeholders. It never receives or stores actual PII.

| Placeholder | Meaning |
|-------------|---------|
| `<EMAIL>` | User's email address |
| `<PHONE>` | User's phone number |
| `<PASSWORD>` | User's password |
| `<PERSON>` | User's full name |
| `<CREDIT_CARD>` | Credit card number |
| `<ACCOUNT_NUMBER>` | Bank account number |
| `<ADDRESS>` | Physical address |
| `<OTP>` | One-time password |

The browser extension resolves placeholders using its local Secure User Vault. The server sends them back as-is in fill actions.

---

## Session Lifecycle

```
Client                          Server
  |                               |
  |--- POST /infer (new id) ----->|
  |    session created            |
  |<-- {actions, checkpoint} -----|
  |                               |
  |  (execute actions)            |
  |  (capture new state)          |
  |                               |
  |--- POST /infer (same id) ---->|
  |    session resumed            |
  |    previous execution validated|
  |    workflow state updated      |
  |<-- {actions, checkpoint} -----|
  |                               |
  |  ... repeat until done ...    |
  |                               |
  |<-- {status: "done"} ----------|
```

**Flow per request:**
1. Session Manager loads or creates session
2. Browser State Validator checks if previous actions succeeded
3. Workflow Manager updates state (retries, phase, summary)
4. Prompt Builder assembles the VLM input
5. Qwen2.5-VL generates structured action JSON
6. Action Validator filters invalid actions
7. Valid actions returned to client

---

## Error Handling

**Repeated failures:** After `MAX_RETRIES` (default 3) consecutive validation failures, the session is blocked.

**Loop detection:** If the browser state hash repeats with high retry count, the session is blocked.

**Blocked session:** Returns `status: "blocked"` with no actions. Client should stop or refresh.

**VLM errors:** Returns `status: "error"` with the error reason. Client can retry.

---

## Timing Metrics

When `DEBUG_TIMINGS=true`, the infer response includes a `timings` object:

| Metric | Description |
|--------|-------------|
| `session_ms` | Time to load/create session from database |
| `validation_ms` | Time to validate previous execution results |
| `workflow_ms` | Time for workflow state updates |
| `prompt_ms` | Time to build the VLM prompt |
| `vlm_ms` | Time for Qwen2.5-VL inference |
| `validation_output_ms` | Time to validate the VLM's action output |
| `total_ms` | End-to-end request time |

---

## cURL Examples

**Health check:**
```bash
curl http://127.0.0.1:8000/health
```

**Create session:**
```bash
curl -X POST http://127.0.0.1:8000/api/v1/session \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sess_001", "task": "Apply for internship"}'
```

**Get session:**
```bash
curl http://127.0.0.1:8000/api/v1/session/sess_001
```

**Delete session:**
```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/session/sess_001
```

**Infer (text-only, no screenshot):**
```bash
curl -X POST http://127.0.0.1:8000/api/v1/infer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_001",
    "task": "Fill the registration form",
    "browser_state": {
      "page": {"title": "Register", "url": "https://example.com/register"},
      "elements": [
        {"element_id": "name", "role": "textbox", "label": "Name", "value": "", "visible": true, "enabled": true},
        {"element_id": "email", "role": "textbox", "label": "Email", "value": "", "visible": true, "enabled": true}
      ]
    }
  }'
```
