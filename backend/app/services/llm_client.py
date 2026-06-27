"""
Thin router that returns the right async LLM client based on the model name.
Supports Anthropic (claude-*) and OpenAI (gpt-*, o1-*, o3-*) models.
"""

from app.core.config import get_settings

settings = get_settings()


def _is_openai_model(model: str) -> bool:
    return model.startswith(("gpt-", "o1-", "o3-", "o4-"))


async def llm_complete(model: str, system: str, user: str, max_tokens: int = 4096) -> str:
    """
    Send a system + user message to the specified model and return the text response.
    Handles provider selection automatically.
    """
    if _is_openai_model(model):
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""
    else:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text
