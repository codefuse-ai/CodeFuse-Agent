#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '/Users/jiawan/projects/CodeFuse-Agent')

print("=== Full TTS Test ===")

# Test the exact same import path as agent_loop.py
from cfuse.core.tts_processor import tts_registry

print("1. Registry from agent_loop import:")
print("   Available modes:", tts_registry.list_processors())
print("   Default:", tts_registry.get_processor('default'))
print("   beam_search:", tts_registry.get_processor('beam_search'))

# Test with the exact same import as main.py
import cfuse.core.tts_modes
print("2. After importing tts_modes:")
print("   Available modes:", tts_registry.list_processors())

# Test the exact command line arguments
print("3. Testing command line parsing...")
import subprocess
result = subprocess.run([
    sys.executable, 
    "-c", 
    """
import sys
sys.path.insert(0, '/Users/jiawan/projects/CodeFuse-Agent')
from cfuse.core.tts_processor import tts_registry
print('CLI test - Available:', tts_registry.list_processors())
print('CLI test - default:', tts_registry.get_processor('default'))
print('CLI test - beam_search:', tts_registry.get_processor('beam_search'))
"""
], capture_output=True, text=True)

print("4. CLI subprocess result:")
print("   stdout:", result.stdout)
print("   stderr:", result.stderr)
print("   returncode:", result.returncode)