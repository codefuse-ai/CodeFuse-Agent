#!/usr/bin/env python3
"""
直接调试脚本 - 逐步执行main.py的逻辑
可以在任何步骤设置断点进行调试
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 现在可以导入需要的模块
from cfuse.config import Config

def debug_step_by_step():
    """逐步调试执行过程"""
    
    print("=== 逐步调试模式 ===")
    
    # 步骤1: 设置参数
    print("\n1. 设置参数...")
    api_key = "y2aLhjtDmLQO33apPi4BSwxT5syrreFK"
    base_url = "https://antnluservice.alipay.com/api/llm/aistudio/v1"
    model = "Kimi-K2-Instruct"
    prompt_file = "/Users/jiawan/projects/CodeFuse-Agent/astropy__astropy-14096.txt"
    logs_dir = "//jiawan/projects/CodeFuse-Agent/workspace/logs"
    
    # 检查文件
    if not os.path.exists(prompt_file):
        print(f"❌ 提示文件不存在: {prompt_file}")
        return
    
    with open(prompt_file, 'r') as f:
        prompt_content = f.read()
    print(f"✅ 提示文件已加载: {len(prompt_content)} 字符")
    
    # 步骤2: 创建配置
    print("\n2. 创建配置...")
    config = Config.load()
    config.llm.api_key = api_key
    config.llm.base_url = base_url
    config.llm.model = model
    config.logging.logs_dir = logs_dir
    config.agent_config.yolo = True
    
    print("✅ 配置已创建")
    
    # 步骤3: 初始化组件
    print("\n3. 初始化组件...")
    try:
        components = initialize_components(config, "default", True, "default")
        print("✅ 组件初始化完成")
        print(f"   - LLM: {components['llm']}")
        print(f"   - 工具数量: {len(components['tool_registry'].list_tool_names())}")
        print(f"   - 会话ID: {components['context_engine'].session_id}")
    except Exception as e:
        print(f"❌ 组件初始化失败: {e}")
        raise
    
    # 步骤4: 运行代理
    print("\n4. 运行代理...")
    try:
        result = run_agent(
            components=components,
            prompt=prompt_content,
            tts_mode="default",
            stream=False,
            verbose=True
        )
        print("✅ 代理运行完成")
        return result
        
    except Exception as e:
        print(f"❌ 代理运行失败: {e}")
        raise

def debug_with_breakpoints():
    """带断点的调试模式"""
    
    # 你可以在这里设置断点
    print("准备开始调试...")
    
    # 断点1: 开始执行前
    print("断点1: 即将开始执行")
    
    # 执行调试
    result = debug_step_by_step()
    
    # 断点2: 执行完成后
    print("断点2: 执行完成")
    
    return result

if __name__ == "__main__":
    print("CodeFuse Agent TTS 调试脚本")
    print("=" * 50)
    print("使用方法:")
    print("1. 在此文件中设置断点 (如 import pdb; pdb.set_trace())")
    print("2. 运行: python debug_tts_direct.py")
    print("3. 或使用pdb: python -m pdb debug_tts_direct.py")
    print("=" * 50)
    
    try:
        result = debug_with_breakpoints()
        print(f"\n调试完成，结果: {result}")
    except Exception as e:
        print(f"\n调试出错: {e}")
        import traceback
        traceback.print_exc()