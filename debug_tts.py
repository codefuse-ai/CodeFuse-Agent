#!/usr/bin/env python3
"""
Debug script for TTS mode issues in CodeFuse Agent
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from cfuse.core.tts_processor import tts_registry
from cfuse.core.tts_modes import register_default_processors

def debug_tts_modes():
    """Debug available TTS modes"""
    print("=== TTS Mode Debug Information ===\n")
    
    # Register default processors
    print("1. Registering default TTS processors...")
    register_default_processors()
    
    # List all registered processors
    print("2. Available TTS processors:")
    processors = tts_registry.list_processors()
    if processors:
        for processor in processors:
            print(f"   - {processor}")
    else:
        print("   No processors registered!")
    
    # Check specific modes
    print("\n3. Checking specific TTS modes:")
    modes_to_check = ["default", "beam_search", "tool_entropy"]
    
    for mode in modes_to_check:
        processor = tts_registry.get_processor(mode)
        if processor:
            print(f"   ✓ {mode}: {processor.__class__.__name__}")
        else:
            print(f"   ✗ {mode}: Not found")
    
    # Check default processor
    print("\n4. Default processor:")
    default = tts_registry.get_processor("default")
    if default:
        print(f"   Default: {default.name} ({default.__class__.__name__})")
    else:
        print("   No default processor set!")

def test_tts_registration():
    """Test TTS processor registration"""
    print("\n=== TTS Registration Test ===\n")
    
    try:
        from cfuse.core.default_tts import DefaultTTSProcessor
        from cfuse.core.beam_search_tts import BeamSearchTTSProcessor
        
        # Create processors
        default_proc = DefaultTTSProcessor()
        beam_proc = BeamSearchTTSProcessor()
        
        print(f"Default processor name: {default_proc.name}")
        print(f"Beam search processor name: {beam_proc.name}")
        
        # Register them
        tts_registry.register(default_proc, is_default=True)
        tts_registry.register(beam_proc)
        
        print("Processors registered successfully!")
        
    except Exception as e:
        print(f"Error during registration: {e}")
        import traceback
        traceback.print_exc()

def check_imports():
    """Check if all required modules can be imported"""
    print("\n=== Import Check ===\n")
    
    modules_to_check = [
        "cfuse.core.tts_processor",
        "cfuse.core.default_tts",
        "cfuse.core.beam_search_tts",
        "cfuse.core.tts_modes"
    ]
    
    for module in modules_to_check:
        try:
            __import__(module)
            print(f"✓ {module}")
        except ImportError as e:
            print(f"✗ {module}: {e}")

if __name__ == "__main__":
    print("CodeFuse Agent TTS Debug Script")
    print("=" * 50)
    
    check_imports()
    test_tts_registration()
    debug_tts_modes()
    
    print("\n=== Debug Complete ===")