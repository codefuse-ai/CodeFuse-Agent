
from cfuse.core.tts_processor import register_tts_processor

from cfuse.core.beam_search_tts import BeamSearchTTSProcessor
from cfuse.core.default_tts import DefaultTTSProcessor


def register_default_processors():
    """Register all default TTS processors"""
    """
    beam_search: concurrent_mode: false  # 使用同步模式
    """
    default_processor = DefaultTTSProcessor()
    beam_search_processor = BeamSearchTTSProcessor(concurrent_mode=True)

    register_tts_processor(default_processor, is_default=True)
    register_tts_processor(beam_search_processor)

# Auto-register processors on import
register_default_processors()
