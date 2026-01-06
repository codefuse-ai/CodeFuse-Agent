from abc import ABC, abstractmethod
from typing import Iterator, Optional, List, Dict, Any
from dataclasses import dataclass

from cfuse.config import Config
from cfuse.llm.base import BaseLLM
from cfuse.tools.registry import ToolRegistry
from cfuse.core.context_engine import ContextEngine




# Forward references to avoid circular imports
AgentEvent = Any


@dataclass
class TTSContext:
    """Context object passed to TTS processors"""
    llm: BaseLLM
    tool_registry: ToolRegistry
    context_engine: ContextEngine
    max_iterations: int
    yolo_mode: bool
    confirmation_callback: Optional[callable] = None
    metrics_collector: Optional[Any] = None
    available_tools: Optional[List[str]] = None
    stream: bool = False
    prompt_tracker: Optional[Any] = None
    branches_file: Optional[str] = None


class BaseTTSProcessor(ABC):
    """Base class for all TTS processors"""
    
    @abstractmethod
    def process(self, context: TTSContext) -> Iterator[Any]:
        """
        Process the TTS mode
        
        Args:
            context: TTS processing context
            
        Yields:
            AgentEvent objects representing processing progress
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this TTS processor"""
        pass


class TTSProcessorRegistry:
    """Registry for TTS processors"""
    
    def __init__(self):
        self._processors: Dict[str, BaseTTSProcessor] = {}
        self._default_processor = None
    
    def register(self, processor: BaseTTSProcessor, is_default: bool = False):
        """
        Register a TTS processor
        
        Args:
            processor: The TTS processor to register
            is_default: Whether this is the default processor
        """
        self._processors[processor.name] = processor
        if is_default:
            self._default_processor = processor
    
    def get_processor(self, name: str) -> Optional[BaseTTSProcessor]:
        """
        Get a TTS processor by name

        Args:
            name: Name of the TTS processor
            
        Returns:
            The TTS processor, or None if not found
        """
        if name == "default":
            return self._default_processor
        return self._processors.get(name)
    
    def list_processors(self) -> List[str]:
        """List all registered TTS processors"""
        return list(self._processors.keys())
    
    def has_processor(self, name: str) -> bool:
        """Check if a TTS processor exists"""
        return name in self._processors or name == "default"


# Global registry instance
tts_registry = TTSProcessorRegistry()


def register_tts_processor(processor: BaseTTSProcessor, is_default: bool = False):
    """
    Convenience function to register a TTS processor
    
    Args:
        processor: The TTS processor to register
        is_default: Whether this is the default processor
    """
    tts_registry.register(processor, is_default)


def get_tts_processor(name: str) -> Optional[BaseTTSProcessor]:
    """
    Convenience function to get a TTS processor
    
    Args:
        name: Name of the TTS processor
        
    Returns:
        The TTS processor, or None if not found
    """
    return tts_registry.get_processor(name)