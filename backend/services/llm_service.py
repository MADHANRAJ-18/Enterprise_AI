from __future__ import annotations

import os

import time

import asyncio

import logging

from datetime import datetime, timezone

from typing import Optional, List, Dict, Any, Union

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

LLM_PROVIDER     = os.getenv("LLM_PROVIDER", "gemini").lower()

GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")

GROQ_API_KEY     = os.getenv("GROQ_API_KEY", "")

LLM_MODEL        = os.getenv("LLM_MODEL", "gemini-2.5-flash")

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

class LLMResponse:
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

def _build_prompt_text(

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

class GeminiLLMService:
    def __init__(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")

        if not api_key:
            logger.warning(

                "GEMINI_API_KEY is not set. Add it to backend/.env to enable Gemini LLM generation."

            )

        self._model_name = os.getenv("LLM_MODEL", "gemini-2.5-flash")

        if self._model_name.startswith("llama"):
            self._model_name = "gemini-2.5-flash"

        self._client: Any = None
        self._sdk_mode: Optional[str] = None
        self._init_client(api_key)

    def _init_client(self, api_key: str):
        if not api_key:
            return

        try:
            from google import genai  # type: ignore

            self._client = genai.Client(api_key=api_key)
            self._sdk_mode = "google-genai"
            logger.info("GeminiLLMService initialised (google-genai SDK): model=%s, temp=%.1f", self._model_name, LLM_TEMPERATURE)

        except ImportError:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(

                    api_key=api_key,

                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"

                )

                self._sdk_mode = "openai-compat"

                logger.info("GeminiLLMService initialised (OpenAI SDK compat): model=%s, temp=%.1f", self._model_name, LLM_TEMPERATURE)

            except ImportError:
                raise ImportError(

                    "Either 'google-genai' or 'openai' package is required. "

                    "Run: pip install google-genai or pip install openai"

                )

    async def generate(

        self,

        user_prompt: str,

        context: Optional[str] = None,

        system_prompt: Optional[str] = None,

        conversation_history: Optional[list] = None,

        attachments: Optional[list] = None,

    ) -> LLMResponse:
        if not user_prompt or not user_prompt.strip():
            raise ValueError("user_prompt cannot be empty.")

        if self._client is None:
            api_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")

            if api_key:
                self._init_client(api_key)

            if self._client is None:
                raise RuntimeError(

                    "GEMINI_API_KEY is not set. "

                    "Add it to backend/.env and restart the server."

                )

        prompt_str = _build_prompt_text(user_prompt, context, attachments)

        start = time.perf_counter()

        response_text, usage, finish_reason = await self._call_with_retry(

            prompt_str=prompt_str,

            system_prompt=system_prompt,

            history=conversation_history or [],

        )

        elapsed = round(time.perf_counter() - start, 3)

        logger.info(

            "Gemini response: %.2fs | prompt_tokens=%s | completion_tokens=%s",

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
        try:
            result = await self.generate("Reply with the single word: OK")

            return {

                "status":     "healthy",

                "model":      self._model_name,

                "provider":   "Google Gemini",

                "response":   result.content[:100],

                "latency_ms": int(result.processing_time * 1000),

            }

        except Exception as exc:
            logger.error("Gemini health check failed: %s", exc)

            return {"status": "unhealthy", "error": str(exc), "model": self._model_name, "provider": "Google Gemini"}

    async def _call_with_retry(

        self,

        prompt_str: str,

        system_prompt: Optional[str],

        history: list,

    ) -> tuple[str, dict, str]:
        wait = LLM_RETRY_WAIT

        for attempt in range(1, LLM_RETRY_MAX + 1):
            try:
                if self._sdk_mode == "google-genai":
                    return await self._single_call_genai(prompt_str, system_prompt, history)

                else:
                    return await self._single_call_openai(prompt_str, system_prompt, history)

            except TimeoutError:
                logger.error("Gemini call timed out after %ds (attempt %d/%d)", LLM_TIMEOUT, attempt, LLM_RETRY_MAX)

                raise

            except Exception as exc:
                err = str(exc).lower()

                is_rate_limit = any(

                    kw in err

                    for kw in ("429", "quota", "rate limit", "resource exhausted", "too many")

                )

                if is_rate_limit and attempt < LLM_RETRY_MAX:
                    logger.warning(

                        "Gemini rate limit (attempt %d/%d) — retrying in %.1fs: %s",

                        attempt, LLM_RETRY_MAX, wait, exc,

                    )

                    await asyncio.sleep(wait)

                    wait *= 2

                else:
                    logger.error("Gemini call failed (attempt %d/%d): %s", attempt, LLM_RETRY_MAX, exc)

                    raise

        raise RuntimeError("Gemini call failed after max retries.")

    async def _single_call_genai(

        self,

        prompt_str: str,

        system_prompt: Optional[str],

        history: list,

    ) -> tuple[str, dict, str]:
        from google.genai import types  # type: ignore

        if self._client is None:
            raise RuntimeError("LLM client is not initialized. Please verify your GEMINI_API_KEY.")

        sys_inst = system_prompt.strip() if system_prompt and system_prompt.strip() else DEFAULT_SYSTEM_PROMPT

        contents = []

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

                gemini_role = "user" if role in ("user", "human") else "model"

                if content.strip():
                    contents.append(types.Content(role=gemini_role, parts=[types.Part.from_text(text=content)]))

        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt_str)]))

        config = types.GenerateContentConfig(

            system_instruction=sys_inst,

            temperature=LLM_TEMPERATURE,

            max_output_tokens=LLM_MAX_TOKENS,

        )

        try:
            response = await asyncio.wait_for(

                self._client.aio.models.generate_content(

                    model=self._model_name,

                    contents=contents,

                    config=config,

                ),

                timeout=LLM_TIMEOUT,

            )

            text = response.text or ""

            usage = {}

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = {

                    "prompt_tokens": getattr(response.usage_metadata, "prompt_token_count", None),

                    "completion_tokens": getattr(response.usage_metadata, "candidates_token_count", None),

                }

            finish_reason = "stop"

            if hasattr(response, "candidates") and response.candidates:
                cand = response.candidates[0]

                if hasattr(cand, "finish_reason") and cand.finish_reason:
                    finish_reason = str(cand.finish_reason.name if hasattr(cand.finish_reason, 'name') else cand.finish_reason).lower()

            return text, usage, finish_reason

        except asyncio.TimeoutError:
            raise TimeoutError(f"Gemini did not respond within {LLM_TIMEOUT}s.")

    async def _single_call_openai(

        self,

        prompt_str: str,

        system_prompt: Optional[str],

        history: list,

    ) -> tuple[str, dict, str]:
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

        messages.append({"role": "user", "content": prompt_str})

        if self._client is None:
            raise RuntimeError("LLM client is not initialized. Please verify your GEMINI_API_KEY.")

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

            usage = {}

            if hasattr(response, "usage") and response.usage:
                usage = {

                    "prompt_tokens": getattr(response.usage, "prompt_tokens", None),

                    "completion_tokens": getattr(response.usage, "completion_tokens", None),

                }

            return text, usage, finish_reason

        except asyncio.TimeoutError:
            raise TimeoutError(f"Gemini did not respond within {LLM_TIMEOUT}s.")

class GroqLLMService:
    def __init__(self) -> None:
        api_key = os.getenv("GROQ_API_KEY", GROQ_API_KEY)

        if not api_key:
            logger.warning(

                "GROQ_API_KEY is not set. Add it to backend/.env to enable Groq LLM generation."

            )

        self._model_name = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

        if self._model_name.startswith("gemini"):
            self._model_name = "llama-3.3-70b-versatile"

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

    async def generate(

        self,

        user_prompt: str,

        context: Optional[str] = None,

        system_prompt: Optional[str] = None,

        conversation_history: Optional[list] = None,

        attachments: Optional[list] = None,

    ) -> LLMResponse:
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

        prompt_str = _build_prompt_text(user_prompt, context, attachments)

        start = time.perf_counter()

        response_text, usage, finish_reason = await self._call_with_retry(

            prompt=prompt_str,

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
        try:
            result = await self.generate("Reply with the single word: OK")

            return {

                "status":     "healthy",

                "model":      self._model_name,

                "provider":   "Groq",

                "response":   result.content[:100],

                "latency_ms": int(result.processing_time * 1000),

            }

        except Exception as exc:
            logger.error("Groq health check failed: %s", exc)

            return {"status": "unhealthy", "error": str(exc), "model": self._model_name, "provider": "Groq"}

    async def _call_with_retry(

        self,

        prompt: str,

        system_prompt: Optional[str],

        history: list,

    ) -> tuple[str, dict, str]:
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

_llm_instance: Optional[Union[GeminiLLMService, GroqLLMService]] = None

def get_llm_service() -> Union[GeminiLLMService, GroqLLMService]:
    global _llm_instance

    if _llm_instance is None:
        provider = os.getenv("LLM_PROVIDER", "").lower()

        gemini_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")

        groq_key = os.getenv("GROQ_API_KEY", "")

        if provider == "groq" or (not provider and groq_key and not gemini_key):
            _llm_instance = GroqLLMService()

        else:
            _llm_instance = GeminiLLMService()

    return _llm_instance

def reset_llm_service() -> None:
    global _llm_instance

    _llm_instance = None
