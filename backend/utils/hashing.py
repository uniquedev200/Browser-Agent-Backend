from __future__ import annotations

import hashlib
import json
from typing import Any


def hash_browser_state(state: dict[str, Any]) -> str:
    canonical = json.dumps(state, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def hash_string(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
