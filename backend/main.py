from __future__ import annotations

import logging
import sys
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from backend.actions.action_validator import ActionValidator
from backend.api.routes import init_routes, router
from backend.config.settings import (
    DATABASE_URL,
    DEBUG_TIMINGS,
    HOST,
    LOG_LEVEL,
    PORT,
    STORAGE_BACKEND,
)
from backend.prompts.prompt_builder import PromptBuilder
from backend.session.session_manager import SessionManager
from backend.storage.memory_store import MemorySessionStore
from backend.utils.logging import setup_logging
from backend.validation.browser_state_validator import BrowserStateValidator
from backend.vlm.qwen_engine import QwenVLMEngine
from backend.workflow.workflow_manager import WorkflowManager

logger = setup_logging(LOG_LEVEL)

vlm_engine = QwenVLMEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting browserauto backend...")

    store = MemorySessionStore()
    pg_store = None

    if STORAGE_BACKEND == "pg" and DATABASE_URL:
        try:
            from backend.storage.pg_store import PGSessionStore

            pg_store = PGSessionStore(DATABASE_URL)
            await pg_store.connect()
            store = pg_store
            logger.info("Using PostgreSQL storage backend")
        except Exception as e:
            logger.warning(
                "Failed to connect to PostgreSQL, falling back to memory: %s", e
            )

    session_manager = SessionManager(store)
    workflow_manager = WorkflowManager()
    state_validator = BrowserStateValidator()
    prompt_builder = PromptBuilder()
    action_validator = ActionValidator()

    try:
        vlm_engine.load()
    except Exception as e:
        logger.error("CRITICAL: Failed to load VLM model: %s", e)
        logger.error("The server will start but inference will fail.")
        logger.error("Ensure the model is at the configured path and GPU is available.")

    init_routes(
        session_manager=session_manager,
        workflow_manager=workflow_manager,
        state_validator=state_validator,
        prompt_builder=prompt_builder,
        vlm_engine=vlm_engine,
        action_validator=action_validator,
        debug_timings=DEBUG_TIMINGS,
    )

    logger.info("Backend ready on %s:%s", HOST, PORT)
    yield

    if pg_store:
        await pg_store.close()
    logger.info("Backend shutdown complete")


app = FastAPI(
    title="BrowserAuto Backend",
    description=(
        "Privacy-preserving browser automation backend.\n\n"
        "Receives sanitized browser state and screenshots, reasons over them using "
        "a local Qwen2.5-VL-3B model, and returns structured browser action plans.\n\n"
        "**No raw PII ever reaches the server.** All personal data arrives as semantic "
        "placeholders like `<EMAIL>`, `<PHONE>`, `<PERSON>`."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "Health",
            "description": "Server health check",
        },
        {
            "name": "Sessions",
            "description": "Create, retrieve, and delete browser automation sessions",
        },
        {
            "name": "Inference",
            "description": "Main agent endpoint — send browser state, receive action plan",
        },
    ],
)

app.include_router(router)


def main() -> None:
    uvicorn.run(
        "backend.main:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level=LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
