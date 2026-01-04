"""
Core Module - Agent loop, context engine (unified context and session management)
"""

from cfuse.core.environment import EnvironmentInfo
from cfuse.core.context_engine import ContextEngine
from cfuse.core.agent_config import AgentProfile, AgentProfileManager
from cfuse.core.read_tracker import ReadTracker
from cfuse.core.agent_loop import AgentLoop, AgentEvent
from cfuse.core.tool_executor import ToolExecutor
from cfuse.observability import (
    setup_logging,
    mainLogger,
    get_session_dir,
    close_all_loggers,
    MetricsCollector,
)

# For backward compatibility, Session is now an alias to ContextEngine
Session = ContextEngine

__all__ = [
    "EnvironmentInfo",
    "ContextEngine",
    "Session",  # Alias for backward compatibility
    "ReadTracker",
    "AgentProfile",
    "AgentProfileManager",
    "AgentLoop",
    "AgentEvent",
    "ToolExecutor",
    "setup_logging",
    "mainLogger",
    "get_session_dir",
    "close_all_loggers",
    "MetricsCollector",
]

