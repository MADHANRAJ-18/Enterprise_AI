"""
backend/services/llm_service.py
─────────────────────────────────────────────────────────────
Module 5 – Groq LLM Integration Service (Llama 3.3 70B Versatile)

Encapsulates all interaction with Groq API using groq or openai SDK.

Key features:
  • Async-native (uses AsyncGroq / AsyncOpenAI)
  • Graceful error handling: rate limits, timeouts, invalid key
  • System prompt injection for enterprise context
  • Configurable via .env — zero hardcoded credentials
  • Singleton pattern (one client per process)
─────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
import time
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────
GROQ_API_KEY     = os.getenv("GROQ_API_KEY", "")
LLM_MODEL        = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_TEMPERATURE  = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS   = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "8192"))
LLM_TIMEOUT      = int(os.getenv("LLM_TIMEOUT_SECONDS", "45"))
LLM_RETRY_MAX    = int(os.getenv("LLM_RETRY_MAX", "3"))
LLM_RETRY_WAIT   = float(os.getenv("LLM_RETRY_WAIT_SECONDS", "2.0"))

DEFAULT_SYSTEM_PROMPT = os.getenv(
    "LLM_SYSTEM_PROMPT",
    (
        "You are an Enterprise AI Knowledge Assistant. "
        "You help employees find accurate information from company documents, "
        "policies, and knowledge bases. "
        "Be concise, professional, and cite relevant context when available. "
        "If you are unsure about something, say so clearly rather than guessing."
    ),
)


# ── LLM Response dataclass ────────────────────────────────────

class LLMResponse:
    """Structured result from a Groq completion call."""

    def __init__(
        self,
        content: str,
        model: str,
        processing_time: float,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        finish_reason: Optional[str] = None,
    ) -> None:
        self.content          = content
        self.model            = model
        self.processing_time  = processing_time
        self.prompt_tokens    = prompt_tokens
        self.completion_tokens = completion_tokens
        self.finish_reason    = finish_reason
        self.timestamp        = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "content":           self.content,
            "model":             self.model,
            "processing_time":   self.processing_time,
            "prompt_tokens":     self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "finish_reason":     self.finish_reason,
            "timestamp":         self.timestamp,
        }


# ── GroqLLMService ───────────────────────────────────────────

class GroqLLMService:
    """
    Singleton service for Groq LLM interactions using groq or openai SDK.
    Default model: llama-3.3-70b-versatile
    """

    def __init__(self) -> None:
        api_key = os.getenv("GROQ_API_KEY", GROQ_API_KEY)
        if not api_key:
            logger.warning(
                "GROQ_API_KEY is not set. Add it to backend/.env to enable LLM generation."
            )

        self._model_name = os.getenv("LLM_MODEL", LLM_MODEL)
        self._client = None
        self._init_client(api_key)

    def _init_client(self, api_key: str):
        if not api_key:
            return

        try:
            from groq import AsyncGroq
            self._client = AsyncGroq(api_key=api_key)
            logger.info("GroqLLMService initialised (Groq SDK): model=%s, temp=%.1f", self._model_name, LLM_TEMPERATURE)
        except ImportError:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=api_key,
                    base_url="https://api.groq.com/openai/v1"
                )
                logger.info("GroqLLMService initialised (OpenAI SDK compat): model=%s, temp=%.1f", self._model_name, LLM_TEMPERATURE)
            except ImportError:
                raise ImportError(
                    "Either 'groq' or 'openai' package is required. "
                    "Run: pip install groq or pip install openai"
                )

    # ── Public API ────────────────────────────────────────────

    async def generate(
        self,
        user_prompt: str,
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[list] = None,
        attachments: Optional[list] = None,
    ) -> LLMResponse:
        """
        Generate a response using Llama 3.3 70B via Groq API.
        """
        if not user_prompt or not user_prompt.strip():
            raise ValueError("user_prompt cannot be empty.")

        if self._client is None:
            api_key = os.getenv("GROQ_API_KEY", "")
            if api_key:
                self._init_client(api_key)
            if self._client is None:
                raise RuntimeError(
                    "GROQ_API_KEY is not set. "
                    "Add it to backend/.env and restart the server."
                )

        prompt = self._build_prompt(user_prompt, context, attachments)

        start = time.perf_counter()
        response_text, usage, finish_reason = await self._call_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            history=conversation_history or [],
        )
        elapsed = round(time.perf_counter() - start, 3)

        logger.info(
            "Groq response: %.2fs | prompt_tokens=%s | completion_tokens=%s",
            elapsed,
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
        )

        return LLMResponse(
            content=response_text,
            model=self._model_name,
            processing_time=elapsed,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            finish_reason=finish_reason,
        )

    async def health_check(self) -> dict:
        """Ping Groq API with a minimal prompt to verify connectivity."""
        try:
            result = await self.generate("Reply with the single word: OK")
            return {
                "status":     "healthy",
                "model":      self._model_name,
                "response":   result.content[:100],
                "latency_ms": int(result.processing_time * 1000),
            }
        except Exception as exc:
            logger.error("Groq health check failed: %s", exc)
            return {"status": "unhealthy", "error": str(exc), "model": self._model_name}

    # ── Internal helpers ──────────────────────────────────────

    def _build_prompt(
        self,
        user_prompt: str,
        context: Optional[str],
        attachments: Optional[list] = None,
    ) -> str:
        parts = []

        if attachments:
            att_sections = []
            for att in attachments:
                fname = att.filename if hasattr(att, 'filename') else att.get('filename', 'Attached Document')
                ftype = att.file_type if hasattr(att, 'file_type') else att.get('file_type', 'Document')
                ftext = att.text if hasattr(att, 'text') else att.get('text', '')
                att_sections.append(
                    f"=== ATTACHED DOCUMENT: {fname} ({ftype}) ===\n"
                    f"{ftext.strip()}\n"
                    f"=== END ATTACHED DOCUMENT: {fname} ==="
                )
            parts.append(
                "The user has attached document(s) directly to this message.\n"
                "Use the attached document content to answer the user's question.\n\n"
                + "\n\n".join(att_sections)
            )

        if context and context.strip():
            parts.append(
                "Use the following retrieved information to answer the question.\n"
                "If the answer isn't in the provided context, say so clearly.\n\n"
                f"--- CONTEXT ---\n{context.strip()}\n--- END CONTEXT ---"
            )

        parts.append(f"Question: {user_prompt.strip()}")
        return "\n\n".join(parts)

    async def _call_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str],
        history: list,
    ) -> tuple[str, dict, str]:
        """Call Groq with exponential-backoff retry on rate-limit errors."""
        wait = LLM_RETRY_WAIT

        for attempt in range(1, LLM_RETRY_MAX + 1):
            try:
                return await self._single_call(prompt, system_prompt, history)
            except TimeoutError:
                logger.error("Groq call timed out after %ds (attempt %d/%d)", LLM_TIMEOUT, attempt, LLM_RETRY_MAX)
                raise
            except Exception as exc:
                err = str(exc).lower()
                is_rate_limit = any(
                    kw in err
                    for kw in ("429", "quota", "rate limit", "resource exhausted", "too many")
                )

                if is_rate_limit and attempt < LLM_RETRY_MAX:
                    logger.warning(
                        "Groq rate limit (attempt %d/%d) — retrying in %.1fs: %s",
                        attempt, LLM_RETRY_MAX, wait, exc,
                    )
                    await asyncio.sleep(wait)
                    wait *= 2
                else:
                    logger.error("Groq call failed (attempt %d/%d): %s", attempt, LLM_RETRY_MAX, exc)
                    raise

        raise RuntimeError("Groq call failed after max retries.")

    async def _single_call(
        self,
        prompt: str,
        system_prompt: Optional[str],
        history: list,
    ) -> tuple[str, dict, str]:
        if self._client is None:
            raise RuntimeError("GROQ_API_KEY is not configured or client failed to initialize.")

        sys_inst = system_prompt.strip() if system_prompt and system_prompt.strip() else DEFAULT_SYSTEM_PROMPT

        messages = [{"role": "system", "content": sys_inst}]

        if history:
            for turn in history:
                if isinstance(turn, dict):
                    role = turn.get("role", "user")
                    parts_raw = turn.get("parts", []) or turn.get("content", "")
                else:
                    role = getattr(turn, "role", "user")
                    parts_raw = getattr(turn, "parts", None) or getattr(turn, "content", "")

                if isinstance(parts_raw, list):
                    content = "\n".join([p if isinstance(p, str) else getattr(p, "text", str(p)) for p in parts_raw])
                else:
                    content = str(parts_raw)

                if role not in ("system", "user", "assistant"):
                    role = "user"

                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": prompt})

        try:
            response = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=self._model_name,
                    messages=messages,
                    temperature=LLM_TEMPERATURE,
                    max_tokens=LLM_MAX_TOKENS,
                ),
                timeout=LLM_TIMEOUT,
            )

            choice = response.choices[0]
            text = choice.message.content or ""
            finish_reason = getattr(choice, "finish_reason", "stop") or "stop"

            usage: dict = {}
            if hasattr(response, "usage") and response.usage:
                usage = {
                    "prompt_tokens": getattr(response.usage, "prompt_tokens", None),
                    "completion_tokens": getattr(response.usage, "completion_tokens", None),
                }

            return text, usage, finish_reason

        except asyncio.TimeoutError:
            raise TimeoutError(f"Groq did not respond within {LLM_TIMEOUT}s.")


# Compatibility Alias
GeminiLLMService = GroqLLMService

# ── Singleton accessor ────────────────────────────────────────

_llm_instance: Optional[GroqLLMService] = None


def get_llm_service() -> GroqLLMService:
    """Return the singleton GroqLLMService (lazy-initialised)."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = GroqLLMService()
    return _llm_instance


def reset_llm_service() -> None:
    """Reset singleton — useful for testing."""
    global _llm_instance
    _llm_instance = None
