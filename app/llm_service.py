import asyncio
import os
from typing import AsyncIterator, List, Optional
import structlog
from langchain_openai import ChatOpenAI
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import RateLimitError, AuthenticationError
from .config import settings
from .utils import FALLBACK_TEXT

logger = structlog.get_logger()

_LLM_INVOKE_TIMEOUT = float(os.getenv("AQUA_LLM_TIMEOUT_SECS", "60"))
_TOKEN_BUFFER_SIZE = int(os.getenv("AQUA_TOKEN_BUFFER_SIZE", "48"))
_TOKEN_FLUSH_INTERVAL = float(os.getenv("AQUA_TOKEN_FLUSH_INTERVAL", "0.05"))


# ---------------------------------------------------
# Helpers Functions
# ---------------------------------------------------
def _lc_messages(messages: List[dict]):
    """Convert plain dict messages into LangChain message objects."""
    lc_msgs = []
    for m in messages:
        role = m["role"].lower()
        if role == "system":
            lc_msgs.append(SystemMessage(content=m["content"]))
        elif role == "user":
            lc_msgs.append(HumanMessage(content=m["content"]))
        elif role == "assistant":
            lc_msgs.append(AIMessage(content=m["content"]))
        else:
            raise ValueError(f"Unsupported role: {role}")
    return lc_msgs


# ---------------------------------------------------
# Streaming from OpenAI
# ---------------------------------------------------
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
async def stream_openai(messages: List[dict], model: str | None) -> AsyncIterator[str]:
    llm = ChatOpenAI(
        model=model or settings.OPENAI_MODEL,
        streaming=True,
        temperature=0.7,
        api_key=settings.OPENAI_API_KEY,
    )

    queue: asyncio.Queue[str] = asyncio.Queue()
    done = asyncio.Event()
    error_marker: Optional[BaseException] = None

    # Small token coalescing buffer for efficiency
    token_buffer: List[str] = []
    last_flush = asyncio.get_event_loop().time()

    class Handler(BaseCallbackHandler):
        """Custom callback handler for streaming tokens."""

        async def on_llm_new_token(self, token: str, **kwargs):
            try:
                await queue.put(token)
            except asyncio.CancelledError:
                raise

        async def on_llm_end(self, *args, **kwargs):
            done.set()

        async def on_llm_error(self, error, **kwargs):
            nonlocal error_marker
            error_marker = error
            logger.error("llm_callback_error", error=str(error))
            done.set()

    handler = Handler()

    async def run_call():
        nonlocal error_marker
        try:
            # Protect the LLM invocation with a timeout so it cannot hang forever
            await asyncio.wait_for(
                llm.ainvoke(_lc_messages(messages), config={"callbacks": [handler]}),
                timeout=_LLM_INVOKE_TIMEOUT,
            )
        except AuthenticationError as ae:
            # Authentication is fatal for this request: map for upstream handling
            logger.error("openai_auth_error", error=str(ae))
            error_marker = PermissionError("Invalid or missing OpenAI API key")
            done.set()
        except RateLimitError as re:
            # Rate limit is transient; push a clear marker and mark done so we can fallback
            logger.error("openai_rate_limit", error=str(re))
            error_marker = re
            try:
                await queue.put("⚠️ OpenAI quota exceeded. Switching to fallback...\n")
            except Exception:
                logger.debug("failed_to_put_rate_limit_marker")
            done.set()
        except asyncio.TimeoutError as te:
            logger.error("openai_invoke_timeout", timeout=_LLM_INVOKE_TIMEOUT)
            error_marker = asyncio.TimeoutError("LLM invocation timed out")
            try:
                await queue.put("⚠️ LLM request timed out. Using fallback...\n")
            except Exception:
                logger.debug("failed_to_put_timeout_marker")
            done.set()
        except Exception as e:
            logger.exception("llm_invoke_unexpected_error", error=str(e))
            error_marker = e
            try:
                await queue.put("⚠️ Unexpected error with LLM backend. Using fallback...\n")
            except Exception:
                logger.debug("failed_to_put_unexpected_error_marker")
            done.set()

    # launch the LLM call in background
    call_task = asyncio.create_task(run_call())

    try:
        while True:
            try:
                token = await asyncio.wait_for(queue.get(), timeout=0.2)
                token_buffer.append(token)

                # flush if buffer gets large enough
                if sum(len(t) for t in token_buffer) >= _TOKEN_BUFFER_SIZE:
                    chunk = "".join(token_buffer)
                    token_buffer.clear()
                    last_flush = asyncio.get_event_loop().time()
                    yield chunk

                # cooperative cancellation check
                if call_task.cancelled():
                    logger.debug("stream_openai_call_task_cancelled")
                    raise asyncio.CancelledError()

            except asyncio.TimeoutError:
                # periodic flush of small buffer for responsiveness
                if token_buffer and (asyncio.get_event_loop().time() - last_flush) >= _TOKEN_FLUSH_INTERVAL:
                    chunk = "".join(token_buffer)
                    token_buffer.clear()
                    last_flush = asyncio.get_event_loop().time()
                    yield chunk

                # if LLM signaled completion and queue is empty → break
                if done.is_set() and queue.empty():
                    break

        # flush any leftover tokens
        if token_buffer:
            yield "".join(token_buffer)
            token_buffer.clear()

        # handle error paths if any
        if error_marker:
            # Authentication -> escalate to upstream handler (main.py expects PermissionError -> 403)
            if isinstance(error_marker, PermissionError):
                # re-raise to allow main.py to map it to 403
                raise error_marker

            # For RateLimit, Timeout, or other errors -> fallback streaming
            logger.warning("stream_openai.falling_back", reason=str(error_marker))
            async for word in stream_fallback():
                yield word

            return
        else:
            # successful completion
            return

    finally:
        # Ensure background task completes and propagate cancellation if needed
        try:
            # give the task a short time to finish cleanly
            await asyncio.wait_for(call_task, timeout=1.0)
        except asyncio.TimeoutError:
            # If it didn't finish promptly, cancel it
            try:
                call_task.cancel()
            except Exception:
                pass
            try:
                await call_task
            except Exception:
                pass
        except asyncio.CancelledError:
            # If we are being cancelled, propagate
            try:
                call_task.cancel()
            except Exception:
                pass
            raise
        except Exception:
            # swallow other cleanup exceptions but log them
            logger.debug("error_waiting_for_call_task_completion", exc_info=True)


# ---------------------------------------------------
# Local fallback streamer
# ---------------------------------------------------
async def stream_fallback() -> AsyncIterator[str]:
    """Yield words from fallback text with small delay."""
    for word in FALLBACK_TEXT.split():
        yield word + " "
        try:
            await asyncio.sleep(0.015)
        except asyncio.CancelledError:
            # stop quickly if the outer context is cancelled (client disconnected)
            logger.debug("stream_fallback.cancelled")
            break
