from __future__ import annotations

import base64
import io
import json
import logging
import re
import time
from typing import Any

import httpx
from PIL import Image

from backend.config.settings import (
    LLAMACPP_URL,
    MAX_IMAGE_HEIGHT,
    MAX_IMAGE_WIDTH,
    MAX_NEW_TOKENS,
)

logger = logging.getLogger("browserauto.vlm")


class LlamaCppEngine:
    def __init__(self) -> None:
        self._loaded = False
        self._client: httpx.AsyncClient | None = None

    async def load(self) -> None:
        logger.info("Connecting to llama-server at %s ...", LLAMACPP_URL)
        start = time.perf_counter()

        self._client = httpx.AsyncClient(base_url=LLAMACPP_URL, timeout=120.0)

        try:
            resp = await self._client.get("/health")
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", "unknown")
                if status == "ok":
                    logger.info("llama-server ready (%.1fs)", time.perf_counter() - start)
                    self._loaded = True
                else:
                    logger.warning("llama-server status: %s", status)
                    self._loaded = True
            else:
                logger.warning("llama-server health check failed: %s", resp.status_code)
                self._loaded = True
        except Exception as e:
            logger.error("Cannot reach llama-server at %s: %s", LLAMACPP_URL, e)
            raise RuntimeError(
                f"llama-server not reachable at {LLAMACPP_URL}. "
                f"Start it with: llama-server --model <gguf> --mmproj <mmproj> --port 8081"
            ) from e

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    def decode_image(self, image_data: str, mime_type: str = "image/png") -> str:
        raw_bytes = base64.b64decode(image_data)
        if len(raw_bytes) > 10 * 1024 * 1024:
            raise ValueError("Image exceeds 10MB limit")

        image = Image.open(io.BytesIO(raw_bytes))
        if image.mode != "RGB":
            image = image.convert("RGB")

        if image.width > MAX_IMAGE_WIDTH or image.height > MAX_IMAGE_HEIGHT:
            image.thumbnail((MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        image.save(buf, format="PNG", optimize=True)
        resized_b64 = base64.b64encode(buf.getvalue()).decode()
        return resized_b64

    async def infer(self, image_b64: str | None, prompt: str) -> dict[str, Any]:
        if not self._loaded:
            raise RuntimeError("LlamaCppEngine not loaded. Call load() first.")

        content: list[dict[str, Any]] = []
        if image_b64:
            resized = self.decode_image(image_b64)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{resized}"},
            })
        content.append({"type": "text", "text": prompt})

        payload = {
            "messages": [
                {"role": "user", "content": content}
            ],
            "max_tokens": MAX_NEW_TOKENS,
            "temperature": 0.1,
        }

        start = time.perf_counter()
        try:
            resp = await self._client.post("/v1/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("llama-server error: %s %s", e.response.status_code, e.response.text[:500])
            return {
                "status": "blocked",
                "phase": "",
                "actions": [],
                "checkpoint": False,
                "reason": f"llama-server error: {e.response.status_code}",
            }
        except Exception as e:
            logger.error("llama-server request failed: %s", e)
            return {
                "status": "blocked",
                "phase": "",
                "actions": [],
                "checkpoint": False,
                "reason": f"llama-server connection error: {e}",
            }

        elapsed = time.perf_counter() - start

        output_text = data["choices"][0]["message"]["content"]
        timings = data.get("timings", {})
        prompt_tokens = timings.get("prompt_tokens", 0)
        completion_tokens = timings.get("predicted_tokens", 0)

        logger.info(
            "VLM inference: %.1fs, %d prompt tokens, %d completion tokens",
            elapsed, prompt_tokens, completion_tokens,
        )
        logger.info("VLM raw output: %s", output_text[:800])

        return self._parse_json_output(output_text)

    def _parse_json_output(self, text: str) -> dict[str, Any]:
        text = text.strip()
        text = re.sub(r"```[\w]*", "", text)
        text = text.strip()

        json_match = re.search(r"\[[\s\S]*\]", text)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_match = re.search(r"\{[\s\S]*", text)
            if not json_match:
                logger.warning("No JSON found in VLM output")
                return {
                    "status": "blocked",
                    "phase": "",
                    "actions": [],
                    "checkpoint": False,
                    "reason": "VLM did not return valid JSON",
                }
            json_str = json_match.group(0)

        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError:
            try:
                fixed = re.sub(r",\s*}", "}", json_str)
                fixed = re.sub(r",\s*]", "]", fixed)
                parsed = json.loads(fixed)
            except json.JSONDecodeError:
                try:
                    fixed = self._repair_truncated_json(json_str)
                    parsed = json.loads(fixed)
                    logger.info("Repaired truncated JSON successfully")
                except Exception as e:
                    logger.warning("Failed to parse VLM JSON: %s", e)
                    return {
                        "status": "blocked",
                        "phase": "",
                        "actions": [],
                        "checkpoint": False,
                        "reason": "VLM returned malformed JSON",
                    }

        if isinstance(parsed, list):
            parsed = {
                "status": "continue",
                "phase": "fill",
                "actions": parsed,
                "checkpoint": True,
                "reason": "filling form",
            }

        required_keys = {"status", "actions"}
        if not required_keys.issubset(parsed.keys()):
            parsed.setdefault("status", "blocked")
            parsed.setdefault("actions", [])
            parsed.setdefault("checkpoint", False)
            parsed.setdefault("reason", "Incomplete VLM output")

        if "elements" in parsed and not parsed["actions"]:
            elements = parsed["elements"]
            actions = []
            i = 1
            if isinstance(elements, dict):
                for key, val in elements.items():
                    if isinstance(val, dict) and val.get("value"):
                        actions.append({
                            "action_id": f"a{i}",
                            "type": "fill",
                            "target": val.get("target", key),
                            "value": val["value"],
                        })
                        i += 1
            parsed["actions"] = actions

        for action in parsed.get("actions", []):
            if action.get("type") in ("check", "uncheck"):
                action.pop("value", None)

        return parsed

    def _repair_truncated_json(self, text: str) -> str:
        fixed = text.rstrip()
        if fixed.endswith(","):
            fixed = fixed[:-1]

        open_quotes = fixed.count('"') - fixed.count('\\"')
        if open_quotes % 2 == 1:
            fixed += '"'

        for _ in range(10):
            try:
                json.loads(fixed)
                return fixed
            except json.JSONDecodeError:
                pass
            close_arr = fixed.count("[") - fixed.count("]")
            close_obj = fixed.count("{") - fixed.count("}")
            total = close_arr + close_obj
            if total <= 0:
                break
            if close_arr > 0 and close_arr >= close_obj:
                fixed += "]"
            elif close_obj > 0:
                fixed += "}"
            elif close_arr > 0:
                fixed += "]"
            else:
                break

        return fixed
