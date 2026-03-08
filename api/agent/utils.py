"""Utility helpers for the BugViper agent."""

import os

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def load_chat_model(model: str) -> BaseChatModel:
    """Load a chat model via OpenRouter. Model format: 'provider/model-name'."""
    provider, model_name = model.split("/", maxsplit=1)
    return init_chat_model(
        model=model_name,
        model_provider=provider,
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=OPENROUTER_BASE_URL,
    )
