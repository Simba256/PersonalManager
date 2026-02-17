"""LLM router — unified interface for OpenAI and Anthropic via LiteLLM."""

from __future__ import annotations

import json
from typing import Optional
from loguru import logger

from app.config import settings


class LLMRouter:
    """Unified LLM interface supporting OpenAI and Anthropic models.

    Falls back gracefully if a provider is not configured.
    Uses litellm for a unified completion API.
    """

    # Model aliases → full litellm model names
    MODEL_ALIASES = {
        # OpenAI
        "gpt-4o": "gpt-4o",
        "gpt-4o-mini": "gpt-4o-mini",
        "gpt-4-turbo": "gpt-4-turbo",
        # Anthropic
        "claude-sonnet": "anthropic/claude-sonnet-4-5-20250929",
        "claude-opus": "anthropic/claude-opus-4-5-20251101",
        "claude-3-7-sonnet": "anthropic/claude-3-7-sonnet-20250219",
        # Default per provider
        "openai-default": "gpt-4o-mini",
        "anthropic-default": "anthropic/claude-sonnet-4-5-20250929",
    }

    def __init__(self):
        self._openai_available = bool(settings.openai_api_key)
        self._anthropic_available = bool(settings.anthropic_api_key)

        if not self._openai_available and not self._anthropic_available:
            logger.warning("No LLM API keys configured. AI features will be unavailable.")

    @property
    def available(self) -> bool:
        return self._openai_available or self._anthropic_available

    @property
    def preferred_model(self) -> str:
        """Return the best available default model."""
        if self._anthropic_available:
            return self.MODEL_ALIASES["anthropic-default"]
        if self._openai_available:
            return self.MODEL_ALIASES["openai-default"]
        return ""

    def _resolve_model(self, model: Optional[str]) -> str:
        """Resolve model alias or auto-select based on availability."""
        if model is None:
            return self.preferred_model
        return self.MODEL_ALIASES.get(model, model)

    def _get_api_key(self, model: str) -> Optional[str]:
        if "anthropic/" in model:
            return settings.anthropic_api_key
        return settings.openai_api_key

    def complete(
        self,
        prompt: str,
        system: str = "",
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> Optional[str]:
        """Generate a completion for a prompt.

        Args:
            prompt: User message
            system: System prompt
            model: Model alias or full litellm model name (auto-selects if None)
            temperature: Sampling temperature (0 = deterministic)
            max_tokens: Max response tokens

        Returns:
            Generated text or None if unavailable
        """
        if not self.available:
            logger.warning("LLM not available — no API keys configured")
            return None

        resolved = self._resolve_model(model)
        if not resolved:
            return None

        try:
            import litellm
            import os

            api_key = self._get_api_key(resolved)
            if api_key:
                if "anthropic/" in resolved:
                    os.environ["ANTHROPIC_API_KEY"] = api_key
                else:
                    os.environ["OPENAI_API_KEY"] = api_key

            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = litellm.completion(
                model=resolved,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"LLM completion failed (model={resolved}): {e}")
            return None

    def complete_json(
        self,
        prompt: str,
        system: str = "",
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 512,
    ) -> Optional[dict]:
        """Generate a completion expected to return valid JSON.

        Returns:
            Parsed dict or None on failure
        """
        result = self.complete(
            prompt=prompt,
            system=system + "\n\nRespond with valid JSON only. No markdown, no explanation.",
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if not result:
            return None

        # Strip markdown code fences if present
        text = result.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"LLM returned invalid JSON: {e}\nRaw: {text[:200]}")
            return None

    def stream(
        self,
        prompt: str,
        system: str = "",
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ):
        """Stream a completion token by token.

        Yields:
            Text chunks as they arrive
        """
        if not self.available:
            return

        resolved = self._resolve_model(model)
        if not resolved:
            return

        try:
            import litellm
            import os

            api_key = self._get_api_key(resolved)
            if api_key:
                if "anthropic/" in resolved:
                    os.environ["ANTHROPIC_API_KEY"] = api_key
                else:
                    os.environ["OPENAI_API_KEY"] = api_key

            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = litellm.completion(
                model=resolved,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            for chunk in response:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content

        except Exception as e:
            logger.error(f"LLM stream failed (model={resolved}): {e}")


# Module-level singleton
_router: Optional[LLMRouter] = None


def get_llm() -> LLMRouter:
    """Get or create the shared LLM router instance."""
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
