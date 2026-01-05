#!/usr/bin/env python3
"""
简化版TTS调试脚本 - 模拟命令行执行
使用方法：
1. 在此脚本中设置断点
2. 运行：python debug_tts_simple.py
3. 使用pdb调试：python -m pdb debug_tts_simple.py
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from cfuse.cli.main import main

def run_debug_session():
    """运行调试会话 - 完全模拟你的命令行参数"""
    
    # 模拟命令行参数
    args = [
        'cfuse/cli/main.py',  # 脚本名
        '--api-key', 'y2aLhjtDmLQO33apPi4BSwxT5syrreFK',
        '--base-url', 'https://antnluservice.alipay.com/api/llm/aistudio/v1',
        '--model', 'Kimi-K2-Instruct',
        '-pp', '/Users/jiawan/projects/CodeFuse-Agent/astropy__astropy-14096.txt',
        '--logs-dir', '/Users/jiawan/projects/CodeFuse-Agent/workspace/logs',
        '--yolo'
    ]
    
    print("=== 调试会话开始 ===")
    print("模拟命令行参数:")
    for i, arg in enumerate(args):
        print(f"  argv[{i}]: {arg}")
    print()
    
    # 设置环境变量
    os.environ['PYTHONPATH'] = '/Users/jiawan/projects/CodeFuse-Agent'
    
    # 保存原始sys.argv
    original_argv = sys.argv.copy()
    
    try:
        # 替换sys.argv
        sys.argv = args
        
        print("正在执行 main() 函数...")
        print("你可以在这里设置断点进行调试")
        print("例如：在 cfuse/cli/main.py 的 main() 函数内设置断点")
        print()
        
        # 调用主函数 - 在这里设置断点
        result = main()
        
        print(f"\n=== 执行完成 ===")
        print(f"返回值: {result}")
        
    except Exception as e:
        print(f"\n=== 执行错误 ===")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 恢复原始sys.argv
        sys.argv = original_argv

if __name__ == "__main__":
    run_debug_session()