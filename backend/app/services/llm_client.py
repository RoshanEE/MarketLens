"""
LLM client with lazy provider initialization.
Supports Anthropic (claude-*) and OpenAI (gpt-*, o1-*, o3-*, o4-*) models.
A single shared instance is returned by get_llm_client().
"""

import structlog
from functools import lru_cache
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from app.core.config import Settings, get_settings

log = structlog.get_logger(__name__)


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._openai: AsyncOpenAI | None = None
        self._anthropic: AsyncAnthropic | None = None

    @property
    def _openai_client(self) -> AsyncOpenAI:
        if self._openai is None:
            self._openai = AsyncOpenAI(api_key=self._settings.openai_api_key)
        return self._openai

    @property
    def _anthropic_client(self) -> AsyncAnthropic:
        if self._anthropic is None:
            self._anthropic = AsyncAnthropic(api_key=self._settings.anthropic_api_key)
        return self._anthropic

    @staticmethod
    def _is_openai(model: str) -> bool:
        return model.startswith(("gpt-", "o1-", "o3-", "o4-"))

    async def complete(self, model: str, system: str, user: str, max_tokens: int = 4096) -> str:
        """Send a system + user prompt to the model and return the text response."""
        log.debug("llm.complete", model=model, max_tokens=max_tokens)

        if self._is_openai(model):
            response = await self._openai_client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=0,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return response.choices[0].message.content or ""
        else:
            response = await self._anthropic_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=0,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    return LLMClient(get_settings())
