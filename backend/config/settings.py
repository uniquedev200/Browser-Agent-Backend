import os
from pathlib import Path

from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(_BASE_DIR / ".env")

MODEL_PATH = os.getenv("MODEL_PATH", r"C:\Users\suraj\Qwen2.5-VL-3B")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "128"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "3600"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DATABASE_URL = os.getenv("DATABASE_URL", "")
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "memory")
DEBUG_TIMINGS = os.getenv("DEBUG_TIMINGS", "false").lower() == "true"

MAX_SCREENSHOT_BYTES = 10 * 1024 * 1024
MAX_IMAGE_WIDTH = 320
MAX_IMAGE_HEIGHT = 320

VALID_PLACEHOLDERS = frozenset({
    "<EMAIL>",
    "<PHONE>",
    "<PASSWORD>",
    "<PERSON>",
    "<CREDIT_CARD>",
    "<ACCOUNT_NUMBER>",
    "<ADDRESS>",
    "<OTP>",
})

SUPPORTED_ACTION_TYPES = frozenset({
    "click",
    "fill",
    "select",
    "check",
    "uncheck",
    "scroll",
    "wait",
    "press_key",
    "upload",
    "done",
})

PAGE_TERMINATING_ACTIONS = frozenset({
    "click",
    "upload",
    "scroll",
})

VALID_SESSION_STATUSES = frozenset({
    "RUNNING",
    "COMPLETED",
    "BLOCKED",
    "ERROR",
})
