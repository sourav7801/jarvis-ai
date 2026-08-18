from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Dict


class ModelProvider(ABC):
    @abstractmethod
    def complete(self, messages: List[Dict[str, str]]) -> str:
        """Return the model's raw text response."""
        raise NotImplementedError


class FunctionModelProvider(ModelProvider):
    """
    Adapter for an existing Jarvis AI function.

    Example:
        provider = FunctionModelProvider(lambda messages: ask_ai(messages))
    """

    def __init__(self, fn):
        self.fn = fn

    def complete(self, messages: List[Dict[str, str]]) -> str:
        return str(self.fn(messages))
