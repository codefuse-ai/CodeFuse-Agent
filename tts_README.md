[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**CFuse - 轻量级、架构清晰的AI代理框架，专为代码分析和研究实验设计**

## ✨ 核心特性

### 可配置代理档案
代理行为通过声明式Markdown档案定义（系统提示词、工具集、模型等），无需代码修改即可快速切换系统提示词和工具子集。

### 双执行模式
- **本地模式**：直接在本地环境执行工具调用
- **HTTP模式**：作为工具执行后端或委托调用到远程沙箱

这种代理决策与环境执行的解耦使CFuse适合作为RL训练流水线的脚手架。

### 内置工具
六个用于代码探索和修改的核心工具：

| 工具 | 描述 |
|------|-------------|
| `read_file` | 读取文件内容，支持可选行范围选择 |
| `write_file` | 创建或覆盖文件 |
| `edit_file` | 通过搜索替换执行编辑 |
| `grep` | 基于ripgrep的快速代码搜索 |
| `glob` | 使用glob模式的文件发现 |
| `bash` | 执行带超时控制的shell命令 |

### 高级TTS模式
- **默认模式**：标准单路径执行
- **束搜索模式** (`beam_search`)：探索多个解决方案路径，支持分支信息记录

## 🏗️ 架构层次

| 层级 | 职责 |
|-------|----------------|
| **交互层** | 终端UI / 无头模式 / HTTP模式 |
| **代理循环** | 核心生命周期：LLM交互、工具调度、迭代控制 |
| **上下文引擎** | 消息历史、环境上下文、压缩、提示词组装 |
| **LLM提供商** | OpenAI兼容API支持 |
| **工具执行** | 6个内置工具 + 远程执行 |
| **可观测性** | 轨迹日志、执行指标、成本跟踪 |

## 📦 安装

```bash
pip install -e .
```

## 🔑 配置

### 必需环境变量
需要配置三个环境变量：

```bash
# 必需：您的OpenAI API密钥（或兼容API密钥）
export OPENAI_API_KEY=your-api-key

# 必需：要使用的LLM模型
export LLM_MODEL=gpt-4o

# 必需：API基础URL
export LLM_BASE_URL=https://api.openai.com/v1
```

**重要说明：**
- 所有三个环境变量都是**必需**的，代理才能正常工作
- `OPENAI_API_KEY` 是唯一使用的API密钥变量
- `LLM_BASE_URL` 可以设置为任何OpenAI兼容的API端点
- `LLM_MODEL` 应该与您的API端点上可用的模型名称匹配

### 配置文件（可选）
您可以选择在项目根目录创建 `.cfuse.yaml` 配置文件或 `~/.cfuse.yaml`：

```yaml
llm:
  provider: openai_compatible
  model: ${LLM_MODEL}           # 使用环境变量
  api_key: ${OPENAI_API_KEY}    # 使用环境变量
  base_url: ${LLM_BASE_URL}     # 使用环境变量
  temperature: 0.0
  max_tokens: null
  timeout: 60

agent_config:
  max_iterations: 200
  max_context_tokens: 128000
  enable_tools: true
  yolo: false
  agent: default
  workspace_root: .
  bash_timeout: 30

logging:
  logs_dir: ~/.cfuse/logs
  verbose: false
  branches_file: null  # 束搜索分支信息保存路径
```

**配置优先级**（从高到低）：
1. CLI参数 (`--model`, `--api-key`, `--base-url` 等)
2. 环境变量 (`OPENAI_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`)
3. 配置文件 (`.cfuse.yaml`)
4. 默认值

## 🚀 快速开始

### 交互模式

```bash
# 基本启动
cfuse

# 启用YOLO模式（自动确认所有工具调用）
cfuse --yolo

# 指定工作空间启动
cfuse --workspace-root /path/to/project
```

### 无头模式

```bash
# 单次查询
cfuse -p "读取README.md并总结它"

# 无需确认自动执行
cfuse -p "分析项目结构" --yolo

# 复杂任务，更多迭代
cfuse -p "重构认证模块" --yolo --max-iterations 300
```

### 使用不同模型

```bash
# 使用特定模型
cfuse --model gpt-4o --api-key sk-xxx --base-url https://api.openai.com/v1

# 使用本地模型（LM Studio、Ollama等）
cfuse --model llama3 --api-key dummy --base-url http://localhost:1234/v1

# 调整温度（0.0 = 确定性，更高 = 创造性）
cfuse -p "修复auth.py中的bug" --temperature 0.0 --yolo
```

### 日志和调试

日志包括 `main.log`、`trajectory/` 和 `llm_messages/` 在 `~/.cfuse/logs` 中

```bash
# 启用详细日志记录
cfuse -p "您的任务" --verbose --yolo

# 自定义日志目录
cfuse -p "您的任务" --logs-dir ./my_logs --yolo
```

### 束搜索模式（高级TTS）

```bash
# 使用束搜索模式探索多个解决方案
cfuse -p "修复这个复杂的bug" --tts beam_search --branches-file ./branches.txt

# 结合YOLO模式自动执行
cfuse -p "重构数据库层" --tts beam_search --yolo --branches-file ./refactor_branches.txt
```

### 常见使用模式

```bash
# 带详细日志的bug修复
cfuse -p "修复认证bug" --workspace-root ./backend --verbose --yolo

# 低温度的代码审查
cfuse -p "审查src/utils/parser.py" --temperature 0.1

# 长时间运行的重构任务
cfuse -p "重构数据库层" --max-iterations 500 --yolo --logs-dir ./refactor_logs

# 会话恢复（加载对话历史）
cfuse --session-id session_20241029_123456_abc123def
```

### HTTP服务器模式

```bash
# 启动HTTP服务器（监听所有接口）
cfuse --http --port 8080

# HTTP服务器（仅本地）
cfuse --http --port 8080 --host 127.0.0.1

# 自定义端口和主机
cfuse --http --host 0.0.0.0 --port 9000
```

### 代理档案管理

```bash
# 列出可用代理
cfuse --list-agents

# 使用特定代理
cfuse -p "调试这个错误" --agent debugger

# 从文件加载代理档案
cfuse -p "帮我完成这个任务" --agent-file ./my_agent.md
```

## ⚙️ CLI选项

### 主要选项

| 选项 | 描述 | 默认值 |
|--------|-------------|---------|
| `-p, --prompt TEXT` | 用户查询（提供时运行无头模式） | `None` |
| `-pp, --prompt-file PATH` | 从文件读取提示词 | `None` |
| `--agent TEXT` | 要使用的代理档案（默认：default） | `default` |
| `--agent-file PATH` | 从Markdown文件加载代理档案 | `None` |
| `--yolo` | YOLO模式：自动确认所有工具调用 | `False` |
| `--workspace-root PATH` | 代理的工作目录 | `.` |
| `--session-id TEXT` | 自定义会话ID（未提供时自动生成） | `None` |

### 模型配置

| 选项 | 描述 | 默认值 |
|--------|-------------|---------|
| `--model TEXT` | LLM模型名称 | `$LLM_MODEL` |
| `--api-key TEXT` | 认证用的API密钥 | `$OPENAI_API_KEY` |
| `--base-url TEXT` | API基础URL | `$LLM_BASE_URL` |
| `--temperature FLOAT` | 模型温度（0.0-2.0，越低越确定） | `0.0` |
| `--max-tokens INT` | 响应中的最大token数 | `null` |
| `--timeout INT` | API请求超时（秒） | `60` |
| `--provider TEXT` | LLM提供商（openai_compatible、anthropic、gemini） | `openai_compatible` |

### TTS和高级模式

| 选项 | 描述 | 默认值 |
|--------|-------------|---------|
| `--tts TEXT` | TTS模式（default、beam_search） | `default` |
| `--branches-file PATH` | 保存束搜索分支信息的文件 | `~/.cfuse/logs/branches.txt` |

### 日志记录

| 选项 | 描述 | 默认值 |
|--------|-------------|---------|
| `--logs-dir PATH` | 日志目录路径 | `~/.cfuse/logs` |
| `-v, --verbose` | 启用详细日志记录 | `False` |
| `--stream / --no-stream` | 启用/禁用流式输出 | `True` |

### HTTP服务器选项

| 选项 | 描述 | 默认值 |
|--------|-------------|---------|
| `--http` | 启用HTTP服务器模式 | `False` |
| `--port INT` | HTTP服务器端口 | `8080` |
| `--host TEXT` | HTTP服务器主机地址 | `0.0.0.0` |
| `--remote-tool-enabled` | 启用通过HTTP的远程工具执行 | `False` |
| `--remote-tool-url TEXT` | 远程工具服务的URL | `None` |
| `--remote-tool-instance-id TEXT` | 远程工具执行的实例ID | `None` |
| `--remote-tool-timeout INT` | 远程工具调用的超时时间（秒） | `60` |

### 其他选项

| 选项 | 描述 |
|--------|-------------|
| `--config PATH` | YAML配置文件路径 |
| `--bash-timeout INT` | bash命令超时（秒，默认：30） |
| `--max-context-tokens INT` | 最大上下文窗口大小（默认：128000） |
| `--enable-tools / --no-tools` | 启用/禁用工具执行 |
| `--list-agents` | 列出可用代理档案并退出 |
| `--help` | 显示帮助信息 |

**配置优先级：** CLI参数 > 环境变量 > 配置文件 > 默认值

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。
