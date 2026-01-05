#!/usr/bin/env python3
"""
Complete debug script for TTS mode issues in CodeFuse Agent
This script replicates the exact command you're trying to run
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from cfuse.config import Config
from cfuse.cli.common import initialize_agent_components
from cfuse.core.tts_processor import tts_registry
from cfuse.core.tts_modes import register_default_processors
from cfuse.core.agent_loop import AgentLoop
from cfuse.llm import create_llm
from cfuse.tools.registry import create_default_registry
def debug_tts_with_real_config():
    """Debug TTS with your exact configuration"""
    print("=== TTS Debug with Real Configuration ===\n")
    
    # Your exact parameters
    api_key = "y2aLhjtDmLQO33apPi4BSwxT5syrreFK"
    base_url = "https://antnluservice.alipay.com/api/llm/aistudio/v1"
    model = "Kimi-K2-Instruct"
    prompt_file = "/Users/jiawan/projects/CodeFuse-Agent/astropy__astropy-14096.txt"
    logs_dir = "/Users/jiawan/projects/CodeFuse-Agent/workspace/logs"
    tts_mode = "default"
    yolo = True
    
    print(f"Configuration:")
    print(f"  API Key: {api_key[:10]}...")
    print(f"  Base URL: {base_url}")
    print(f"  Model: {model}")
    print(f"  Prompt File: {prompt_file}")
    print(f"  Logs Dir: {logs_dir}")
    print(f"  TTS Mode: {tts_mode}")
    print(f"  YOLO: {yolo}")
    print()
    
    # Check if prompt file exists
    if not os.path.exists(prompt_file):
        print(f"❌ Prompt file not found: {prompt_file}")
        return
    
    # Read prompt content
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            prompt_content = f.read().strip()
        print(f"✅ Prompt file loaded ({len(prompt_content)} chars)")
    except Exception as e:
        print(f"❌ Error reading prompt file: {e}")
        return
    
    # Test TTS registry
    print("\n1. Testing TTS Registry...")
    register_default_processors()
    
    available_processors = tts_registry.list_processors()
    print(f"   Available processors: {available_processors}")
    
    processor = tts_registry.get_processor(tts_mode)
    if processor:
        print(f"   ✅ Found processor for '{tts_mode}': {processor.__class__.__name__}")
    else:
        print(f"   ❌ No processor found for '{tts_mode}'")
        print(f"   Available: {available_processors}")
        return
    
    # Test configuration loading
    print("\n2. Testing Configuration...")
    try:
        cfg = Config.load()
        print("   ✅ Config loaded successfully")
        
        # Override with your settings
        cfg.llm.api_key = api_key
        cfg.llm.base_url = base_url
        cfg.llm.model = model
        cfg.logging.logs_dir = logs_dir
        cfg.agent_config.yolo = yolo
        
        # Validate config
        errors = cfg.validate()
        if errors:
            print(f"   ❌ Config validation errors:")
            for error in errors:
                print(f"     - {error}")
            return
        else:
            print("   ✅ Config validation passed")
            
    except Exception as e:
        print(f"   ❌ Config error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test component initialization
    print("\n3. Testing Component Initialization...")
    try:
        components = initialize_agent_components(
            cfg=cfg,
            agent_name="default",
            verbose=True,
            tts=tts_mode
        )
        print("   ✅ Components initialized successfully")
        
        # Extract key components
        llm = components["llm"]
        tool_registry = components["tool_registry"]
        context_engine = components["context_engine"]
        
        print(f"   LLM: {llm}")
        print(f"   Tools: {len(tool_registry.list_tool_names())} available")
        print(f"   Session: {context_engine.session_id}")
        
    except Exception as e:
        print(f"   ❌ Component initialization error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test AgentLoop creation
    print("\n4. Testing AgentLoop...")
    try:
        agent_loop = AgentLoop(
            llm=llm,
            tool_registry=tool_registry,
            context_engine=context_engine,
            max_iterations=cfg.agent_config.max_iterations,
            yolo_mode=cfg.agent_config.yolo,
            metrics_collector=components["metrics_collector"]
        )
        print("   ✅ AgentLoop created successfully")
        
        # Test TTS processor lookup within AgentLoop
        processor = tts_registry.get_processor(tts_mode)
        if processor:
            print(f"   ✅ AgentLoop can use '{tts_mode}' processor")
        else:
            print(f"   ❌ AgentLoop cannot find '{tts_mode}' processor")
            
    except Exception as e:
        print(f"   ❌ AgentLoop error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n5. Running test with your prompt...")
    try:
        # Run a simple test
        events = list(agent_loop.run(prompt_content, stream=False, tts=tts_mode))
        
        # Check for errors
        errors = [e for e in events if e.type == "error"]
        if errors:
            print(f"   ❌ Errors during execution:")
            for error in errors:
                print(f"     - {error.data}")
        else:
            print("   ✅ Test execution completed successfully")
            
            # Show final response
            done_events = [e for e in events if e.type == "agent_done"]
            if done_events:
                final_response = done_events[0].data.get("final_response", "")
                print(f"   Final response: {final_response[:200]}...")
                
    except Exception as e:
        print(f"   ❌ Test execution error: {e}")
        import traceback
        traceback.print_exc()

def test_individual_components():
    """Test individual components step by step"""
    print("\n=== Individual Component Test ===\n")
    
    # Test 1: TTS Registry
    print("1. TTS Registry Test:")
    try:
        register_default_processors()
        print("   ✅ Default processors registered")
        
        for mode in ["default", "beam_search"]:
            proc = tts_registry.get_processor(mode)
            if proc:
                print(f"   ✅ {mode}: {proc.name}")
            else:
                print(f"   ❌ {mode}: Not found")
                
    except Exception as e:
        print(f"   ❌ Registry error: {e}")
    
    # Test 2: LLM Creation
    print("\n2. LLM Creation Test:")
    try:
        llm = create_llm(
            model="Kimi-K2-Instruct",
            api_key="y2aLhjtDmLQO33apPi4BSwxT5syrreFK",
            base_url="https://antnluservice.alipay.com/api/llm/aistudio/v1",
            provider="openai_compatible"
        )
        print(f"   ✅ LLM created: {llm}")
    except Exception as e:
        print(f"   ❌ LLM creation error: {e}")
    
    # Test 3: Tool Registry
    print("\n3. Tool Registry Test:")
    try:
        registry = create_default_registry(
            workspace_root=Path.cwd(),
            read_tracker=None,
            config=None
        )
        tools = registry.list_tool_names()
        print(f"   ✅ Tools loaded: {len(tools)} tools")
        for tool in tools[:5]:  # Show first 5
            print(f"     - {tool}")
    except Exception as e:
        print(f"   ❌ Tool registry error: {e}")

if __name__ == "__main__":
    print("CodeFuse Agent TTS Debug Script")
    print("=" * 50)
    
    test_individual_components()
    debug_tts_with_real_config()
    
    print("\n" + "=" * 50)
    print("Debug Complete")