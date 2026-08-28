from __future__ import annotations

import base64
import io
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Optional

from PIL import Image

from backend.config.settings import MAX_IMAGE_HEIGHT, MAX_IMAGE_WIDTH, MAX_NEW_TOKENS, MODEL_PATH

logger = logging.getLogger("browserauto.vlm")


class QwenVLMEngine:
    def __init__(self) -> None:
        self._model: Any = None
        self._processor: Any = None
        self._loaded = False
        self._device: str = "cpu"
        self._torch: Any = None
        self._model_type: str = "qwen2_5_vl"

    def load(self) -> None:
        logger.info("Loading model from %s ...", MODEL_PATH)
        start = time.perf_counter()

        try:
            import torch
            from transformers import AutoProcessor
            self._torch = torch
        except ImportError as e:
            raise RuntimeError(
                "Required packages not found. Install with: "
                "pip install torch transformers accelerate bitsandbytes"
            ) from e

        try:
            from transformers import BitsAndBytesConfig

            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.float16,
            )
            logger.info("Using 4-bit NF4 quantization")
        except ImportError as e:
            raise RuntimeError(
                "bitsandbytes is required for 4-bit quantization. "
                "Install with: pip install bitsandbytes"
            ) from e

        model_path = Path(MODEL_PATH)
        config_file = model_path / "config.json"
        if config_file.exists():
            with open(config_file) as f:
                config = json.load(f)
            model_type = config.get("model_type", "")
            architectures = config.get("architectures", [])
        else:
            model_type = ""
            architectures = []

        if "Qwen2VLForConditionalGeneration" in architectures or model_type == "qwen2_vl":
            from transformers import Qwen2VLForConditionalGeneration
            model_cls = Qwen2VLForConditionalGeneration
            self._model_type = "qwen2_vl"
            logger.info("Detected Qwen2-VL architecture")
        else:
            from transformers import Qwen2_5_VLForConditionalGeneration
            model_cls = Qwen2_5_VLForConditionalGeneration
            self._model_type = "qwen2_5_vl"
            logger.info("Detected Qwen2.5-VL architecture")

        try:
            self._model = model_cls.from_pretrained(
                MODEL_PATH,
                quantization_config=quantization_config,
                device_map="auto",
                trust_remote_code=True,
                attn_implementation="sdpa",
            )
            self._processor = AutoProcessor.from_pretrained(
                MODEL_PATH,
                trust_remote_code=True,
            )
        except Exception as e:
            error_msg = str(e)
            raise RuntimeError(
                f"Failed to load model from {MODEL_PATH}: {error_msg}"
            ) from e

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._loaded = True
        elapsed = time.perf_counter() - start
        logger.info("Model loaded in %.1fs on %s (%s)", elapsed, self._device, self._model_type)

        compile_start = time.perf_counter()
        try:
            logger.info("Skipping torch.compile for stability")
        except Exception as e:
            logger.warning("torch.compile failed, continuing without: %s", e)

    def decode_image(self, image_data: str, mime_type: str = "image/png") -> Image.Image:
        raw_bytes = base64.b64decode(image_data)
        if len(raw_bytes) > 10 * 1024 * 1024:
            raise ValueError("Image exceeds 10MB limit")

        image = Image.open(io.BytesIO(raw_bytes))

        if image.mode != "RGB":
            image = image.convert("RGB")

        if image.width > MAX_IMAGE_WIDTH or image.height > MAX_IMAGE_HEIGHT:
            image.thumbnail((MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT), Image.Resampling.LANCZOS)

        return image

    def infer(self, image: Image.Image | None, prompt: str) -> dict[str, Any]:
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        torch = self._torch

        start = time.perf_counter()

        if image is not None:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": image},
                        {"type": "text", "text": prompt},
                    ],
                }
            ]
        else:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                    ],
                }
            ]

        text = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        if image is not None:
            inputs = self._processor(
                text=[text],
                images=[image],
                return_tensors="pt",
                padding=True,
            )
        else:
            inputs = self._processor(
                text=[text],
                return_tensors="pt",
                padding=True,
            )

        inputs = inputs.to(self._model.device)

        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                use_cache=True,
            )

        input_len = inputs["input_ids"].shape[1]
        generated = output_ids[0][input_len:]
        output_text = self._processor.decode(generated, skip_special_tokens=True)

        elapsed = time.perf_counter() - start
        logger.debug("VLM inference took %.2fs", elapsed)

        return self._parse_json_output(output_text)

    def _parse_json_output(self, text: str) -> dict[str, Any]:
        text = text.strip()

        text = re.sub(r"```[\w]*", "", text)
        text = text.strip()

        json_match = re.search(r"\{[\s\S]*", text)
        if not json_match:
            logger.warning("No JSON found in VLM output, returning fallback")
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
                    logger.warning("Failed to parse VLM JSON output: %s", e)
                    return {
                        "status": "blocked",
                        "phase": "",
                        "actions": [],
                        "checkpoint": False,
                        "reason": "VLM returned malformed JSON",
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
