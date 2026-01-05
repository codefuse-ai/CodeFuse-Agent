
from codefuse.core.beam_search_tts import BeamSearchTTSProcessor
from codefuse.core.default_tts import DefaultTTSProcessor
from codefuse.core.tts_processor import register_tts_processor

def register_default_processors(judge_llm=None):
    """Register all default TTS processors"""
    """
    beam_search: concurrent_mode: false  # 使用同步模式
    """
    default_processor = DefaultTTSProcessor()
    beam_search_processor = BeamSearchTTSProcessor(concurrent_mode=True, judge_llm=judge_llm)

    register_tts_processor(default_processor, is_default=True)
    register_tts_processor(beam_search_processor)

# Auto-register processors on import (without judge_llm)
register_default_processors()
