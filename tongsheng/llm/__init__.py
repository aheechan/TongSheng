"""Local OpenAI-compatible LLM client and llama.cpp server supervision."""

from .client import ChatClient, LLMError, strip_thinking
from .servers import LlamaServer, ServerError, ServerManager, ServerSpec

__all__ = ["ChatClient", "LLMError", "strip_thinking",
           "LlamaServer", "ServerManager", "ServerSpec", "ServerError"]
