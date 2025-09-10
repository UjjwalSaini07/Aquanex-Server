from __future__ import annotations

import asyncio
import orjson
import structlog
from fastapi import FastAPI, Request, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from .config import settings
from .auth import verify_header_auth
from .logging_conf import setup_logging
from .middlewares import log_requests
from .schemas import ChatRequest, ErrorResponse
from .utils import includes_any, INFORMAL_PATTERNS, ALLOWED_TOPICS
from .llm_service import stream_openai, stream_fallback
from .redis_client import get_redis, cache_key_from_prompt

setup_logging()
logger = structlog.get_logger()

app = FastAPI(title=settings.APP_NAME)

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if origins == ["*"] else origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(log_requests)


# Routes
@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "chat": "/chat (POST)",
            "health": "/health (GET)",
        },
    }


@app.get("/health")
async def health():
    """Simple health check."""
    return {"status": "ok"}


@app.post("/chat", responses={500: {"model": ErrorResponse}})
async def chat(payload: ChatRequest, token: str = Depends(verify_header_auth)):
    try:
        messages = [m.model_dump() for m in payload.messages]
        selected_model = payload.selectedModel

        latest = (messages[-1]["content"] or "").lower() if messages else ""
        is_informal = includes_any(latest, INFORMAL_PATTERNS)
        is_allowed = includes_any(latest, ALLOWED_TOPICS)

        r = await get_redis()
        cache_key = cache_key_from_prompt(latest, selected_model or settings.OPENAI_MODEL)

        async def stream_result(gen):
            """Helper: stream tokens & cache final output if Redis available."""
            full: list[str] = []
            try:
                async for chunk in gen:
                    full.append(chunk)
                    yield chunk
            finally:
                if r is not None and full:
                    try:
                        await r.set(cache_key, "".join(full), ex=60 * 30)
                    except Exception as e:
                        logger.warning("redis_set_failed", error=str(e))

        # Restrict content (if not allowed → fallback model)
        if not (is_informal or is_allowed):
            return StreamingResponse(
                stream_result(stream_fallback()),
                media_type="text/plain; charset=utf-8",
            )

        # Redis cache lookup
        if r is not None:
            try:
                cached = await r.get(cache_key)
                if cached:
                    async def stream_cached():
                        text = cached.decode("utf-8") if isinstance(cached, bytes) else cached  
                        for ch in text:
                            yield ch
                            await asyncio.sleep(0)

                    return StreamingResponse(
                        stream_cached(),
                        media_type="text/plain; charset=utf-8",
                    )
            except Exception as e:
                logger.warning("redis_get_failed", error=str(e))

        # Fallback: stream from OpenAI
        return StreamingResponse(
            stream_result(stream_openai(messages, selected_model)),
            media_type="text/plain; charset=utf-8",
        )

    except ValueError as e:
        logger.warning("validation_error", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(error=str(e)).model_dump(),
        )
    except PermissionError as e:
        logger.error("openai_auth_or_quota_error", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=ErrorResponse(error=str(e)).model_dump(),
        )
    except Exception as e:
        logger.exception("chat_error", error=str(e))
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(error="Internal server error").model_dump(),
        )
