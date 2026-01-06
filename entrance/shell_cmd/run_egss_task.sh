#!/bin/bash

# CFuse Astropy任务运行脚本
# 该脚本在当前工程目录，但切换到修复路径下运行

set -e

# 定义路径
ASTROPY_PATH="" #修复的repo路径
CFUSE_PATH="" #CFuse路径

# 检查astropy目录是否存在
if [ ! -d "$ASTROPY_PATH" ]; then
    echo "错误: Astropy目录 $ASTROPY_PATH 不存在"
    exit 1
fi

# 检查cfuse目录是否存在
if [ ! -d "$CFUSE_PATH" ]; then
    echo "错误: CFuse目录 $CFUSE_PATH 不存在"
    exit 1
fi

echo "=========================================="
echo "CFuse Astropy任务运行脚本"
echo "=========================================="
echo "当前时间: $(date)"
echo "修复路径: $ASTROPY_PATH"
echo "CFuse路径: $CFUSE_PATH"
echo "=========================================="

# 切换到astropy目录
cd "$ASTROPY_PATH"

echo "已切换到目录: $(pwd)"
echo "开始运行CFuse任务..."
echo ""

# 设置PYTHONPATH并运行CFuse命令
PYTHONPATH="$CFUSE_PATH" python "$CFUSE_PATH/cfuse/cli/main.py" \
    --api-key "" \
    --base-url "" \
    --model "" \
    -pp "$CFUSE_PATH/entrance/shell_cmd/astropy__astropy-14096.txt" \
    --logs-dir "$CFUSE_PATH/workspace/logs" \
    --yolo \
    --tts beam_search \
    --branches-file "$CFUSE_PATH/workspace/logs/branches.txt"

echo ""
echo "=========================================="
echo "任务完成!"
echo "=========================================="
echo "返回原始目录: $CFUSE_PATH"
cd "$CFUSE_PATH"