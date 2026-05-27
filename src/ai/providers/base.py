"""
base.py -- BaseAIProvider abstract interface.

All concrete providers implement complete() and is_available.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAIProvider(ABC):
    """
    Abstract base for AI completion providers.

    Design rules:
    - complete() NEVER raises in production -- errors are caught and "" is returned.
    - When api_key is absent, is_available returns False and complete() returns ""
      immediately without any network call.
    - All providers accept an injectable ``client`` parameter for unit testing.
    """

    @abstractmethod
    async def complete(self, prompt: str, *, max_tokens: int, model: str) -> str:
        """
        Run a completion and return the response text.

        Returns "" if the provider is unavailable or the API call fails.
        Never raises.
        """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """True when an API key is configured."""
