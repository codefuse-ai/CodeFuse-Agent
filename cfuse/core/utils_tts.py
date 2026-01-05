from typing import List, Any, Dict, Optional
from dataclasses import dataclass, field
from cfuse.core.agent_loop import AgentEvent
from pathlib import Path
from cfuse.llm.base import LLMResponse
import json

@dataclass
class BeamPath:
    """Beam search path state management"""
    path_id: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    score: Optional[float] = None
    is_stopped: str = "continue"
    step: int = 0
    run_workspace: Optional[Path] = None
    parent_path_id: Optional[str] = None
    commit_id: str = ""
    parent_commit_id: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    response: Optional[LLMResponse] = None
    compression_history: List[Dict[str, Any]] = field(default_factory=list)


def _handle_streaming_llm(llm, messages, tools, session_id, metrics_collector):
    """Handle streaming LLM response"""

    content_parts = []
    tool_calls = []
    usage = None
    finish_reason = ""

    # Track API call if metrics collector is available
    if metrics_collector:
        api_tracker_ctx = metrics_collector.track_api_call()
        api_tracker = api_tracker_ctx.__enter__()
    else:
        api_tracker_ctx = None
        api_tracker = None

    try:
        stream = llm.generate(
            messages=messages,
            tools=tools,
            stream=True,
        )

        for chunk in stream:
            if chunk.type == "content":
                content_parts.append(chunk.delta)
                # Yield immediately for streaming
                yield AgentEvent(type="llm_chunk", data={"delta": chunk.delta})

            elif chunk.type == "tool_call":
                tool_calls.append(chunk.tool_call)

            elif chunk.type == "done":
                usage = chunk.usage
                finish_reason = chunk.finish_reason

        # Reconstruct LLMResponse
        response = LLMResponse(
            content="".join(content_parts),
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=finish_reason,
        )

        # Record metrics if tracking
        if api_tracker and usage:
            api_tracker.set_tokens(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                cache_creation_tokens=usage.cache_creation_input_tokens,
                cache_read_tokens=usage.cache_read_input_tokens,
            )

        if api_tracker and finish_reason:
            api_tracker.set_finish_reason(finish_reason)

        # Yield final done event
        yield AgentEvent(
            type="llm_done",
            data={
                "content": response.content,
                "has_tool_calls": response.has_tool_calls,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": tc.function,
                    }
                    for tc in tool_calls
                ] if tool_calls else [],
                "session_id": session_id,
            }
        )

        # Return the response for the caller
        return response

    finally:
        if api_tracker_ctx:
            api_tracker_ctx.__exit__(None, None, None)


def _get_tool_signature(tool_call) -> str:
    func_name = tool_call.function.get("name", "")

    try:
        if isinstance(tool_call.function.get("arguments"), str):
            func_args = json.loads(tool_call.function.get("arguments", "{}"))
        else:
            func_args = tool_call.function.get("arguments", {})
    except (json.JSONDecodeError, TypeError):
        func_args = {}

    key_param = None
    if func_name == "edit_file":
        key_param = func_args.get("file_path")
    elif func_name == "glob":
        key_param = func_args.get("path")
    elif func_name == "grep":
        key_param = func_args.get("path")
    elif func_name == "read_file":
        key_param = func_args.get("path")
    elif func_name == "write_file":
        key_param = func_args.get("path")

    return f"{func_name}:{key_param}" if key_param is not None else func_name
