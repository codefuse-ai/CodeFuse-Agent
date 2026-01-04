"""
LLM Module - Unified interface for various language models
"""

from cfuse.llm.base import (
    BaseLLM,
    Message,
    MessageRole,
    ContentBlock,
    Tool,
    ToolCall,
    TokenUsage,
    LLMResponse,
    LLMChunk,
)
from cfuse.llm.factory import create_llm
from cfuse.llm.exceptions import (
    LLMError,
    RetryableError,
    TimeoutError,
    RateLimitError,
    APIError,
    AuthenticationError,
    ContextLengthExceededError,
)

__all__ = [
    # Base classes and data structures
    "BaseLLM",
    "Message",
    "MessageRole",
    "ContentBlock",
    "Tool",
    "ToolCall",
    "TokenUsage",
    "LLMResponse",
    "LLMChunk",
    # Factory
    "create_llm",
    # Exceptions
    "LLMError",
    "RetryableError",
    "TimeoutError",
    "RateLimitError",
    "APIError",
    "AuthenticationError",
    "ContextLengthExceededError",
]

