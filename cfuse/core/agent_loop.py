"""
Agent Loop - Main agent execution loop with tool calling
"""

from dataclasses import dataclass
from typing import Iterator, List, Optional, Literal, Any, Callable, Union

from cfuse import config
from cfuse.core.tts_processor import tts_registry, TTSContext

from cfuse.llm.base import BaseLLM, Message, ContentBlock
from cfuse.tools.registry import ToolRegistry
from cfuse.core.context_engine import ContextEngine
from cfuse.core.tool_executor import ToolExecutor
from cfuse.observability import MetricsCollector, mainLogger


@dataclass
class AgentEvent:
    """
    Event emitted by the agent loop

    Events allow streaming updates to the caller about agent progress.
    """
    type: Literal[
        "llm_start",  # LLM call started
        "llm_chunk",  # Streaming chunk from LLM
        "llm_done",  # LLM call completed
        "tool_confirmation_required",  # Tool needs user confirmation
        "tool_start",  # Tool execution started
        "tool_done",  # Tool execution completed
        "agent_done",  # Agent loop completed
        "agent_think",  # Agent thinking/reasoning message
        "error",  # Error occurred
    ]
    data: Any  # Type depends on event type


class AgentLoop:
    """
    Main agent execution loop

    Handles:
    - LLM interaction
    - Tool calling and execution
    - User confirmation for dangerous tools
    - Streaming output
    """

    def __init__(
            self,
            llm: BaseLLM,
            tool_registry: ToolRegistry,
            context_engine: ContextEngine,
            max_iterations: int = 10,
            yolo_mode: bool = False,
            confirmation_callback: Optional[Callable[[str, str, dict], bool]] = None,
            metrics_collector: Optional[MetricsCollector] = None,
            remote_tool_enabled: bool = False,
            remote_tool_url: Optional[str] = None,
            remote_tool_instance_id: Optional[str] = None,
            remote_tool_timeout: int = 60,
            branches_file: Optional[str] = None,
    ):
        """
        Initialize agent loop

        Args:
            llm: LLM instance
            tool_registry: Tool registry
            context_engine: Context engine
            max_iterations: Maximum number of iterations
            yolo_mode: If True, auto-confirm all tool executions
            confirmation_callback: Callback for tool confirmation
                                  (tool_name, tool_id, arguments) -> bool
            metrics_collector: Optional metrics collector for tracking performance
            remote_tool_enabled: If True, use remote tool execution
            remote_tool_url: URL of remote tool service
            remote_tool_instance_id: Instance ID for remote execution
            remote_tool_timeout: Timeout for remote tool calls in seconds
            branches_file: Optional file path to save beam search branches information
        """
        self.llm = llm
        self.tool_registry = tool_registry
        self.context_engine = context_engine
        self.max_iterations = max_iterations
        self.yolo_mode = yolo_mode
        self.confirmation_callback = confirmation_callback
        self.metrics_collector = metrics_collector

        # Initialize tool executor
        self.tool_executor = ToolExecutor(
            tool_registry=tool_registry,
            context_engine=context_engine,
            yolo_mode=yolo_mode,
            confirmation_callback=confirmation_callback,
            metrics_collector=metrics_collector,
            remote_enabled=remote_tool_enabled,
            remote_url=remote_tool_url,
            remote_instance_id=remote_tool_instance_id,
            remote_timeout=remote_tool_timeout,
        )
        
        self.branches_file = branches_file

        mainLogger.info(
            "AgentLoop initialized",
            session_id=self.context_engine.session_id,
            max_iterations=max_iterations,
            yolo_mode=yolo_mode,
            temperature=llm.temperature if hasattr(llm, 'temperature') else None,
        )

    @property
    def session_id(self) -> str:
        """Get session ID from context engine"""
        return self.context_engine.session_id

    def _build_llm_done_event_data(self, llm_response) -> dict:
        """
        Build llm_done event data from LLM response

        Args:
            llm_response: LLM response object

        Returns:
            Dictionary with event data
        """
        return {
            "content": llm_response.content,
            "has_tool_calls": llm_response.has_tool_calls,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": tc.function,
                }
                for tc in llm_response.tool_calls
            ] if llm_response.tool_calls else [],
            "session_id": self.session_id,
        }

    def _record_llm_metrics(self, api_tracker, llm_response) -> None:
        """
        Record LLM call metrics

        Args:
            api_tracker: API tracker from metrics collector
            llm_response: LLM response object
        """
        if not api_tracker:
            return

        if llm_response.usage:
            api_tracker.set_tokens(
                prompt_tokens=llm_response.usage.prompt_tokens,
                completion_tokens=llm_response.usage.completion_tokens,
                total_tokens=llm_response.usage.total_tokens,
                cache_creation_tokens=llm_response.usage.cache_creation_input_tokens,
                cache_read_tokens=llm_response.usage.cache_read_input_tokens,
            )

        if llm_response.model:
            api_tracker.set_model(llm_response.model)

        if llm_response.finish_reason:
            api_tracker.set_finish_reason(llm_response.finish_reason)

    @staticmethod
    def _summarize_query(user_query: Union[str, List[ContentBlock]]) -> str:
        """
        Generate a short summary of user query for logging

        Args:
            user_query: User query (text or multimodal content blocks)

        Returns:
            Query summary string
        """
        if isinstance(user_query, str):
            return user_query[:100] if len(user_query) > 100 else user_query
        else:
            # Multimodal content
            text_parts = [
                block.text for block in user_query
                if block.type == "text" and block.text
            ]
            image_count = sum(
                1 for block in user_query
                if block.type == "image_url"
            )
            text_preview = text_parts[0][:50] if text_parts else ""
            return f"{text_preview}... [{image_count} image(s)]"

    def _call_llm(self, messages: List[Message], tools: List, stream: bool):
        """
        Unified LLM call interface with metrics tracking

        Args:
            messages: Messages to send
            tools: Tools available
            stream: Whether to stream responses

        Returns:
            If stream=False: LLMResponse
            If stream=True: Generator
        """
        if not stream:
            # Non-streaming: call directly and record metrics
            if self.metrics_collector:
                with self.metrics_collector.track_api_call() as api_tracker:
                    llm_response = self.llm.generate(
                        messages=messages,
                        tools=tools,
                        stream=False,
                    )
                    self._record_llm_metrics(api_tracker, llm_response)
            else:
                llm_response = self.llm.generate(
                    messages=messages,
                    tools=tools,
                    stream=False,
                )
            return llm_response
        else:
            # Streaming: return generator
            return self.llm.generate(
                messages=messages,
                tools=tools,
                stream=True,
            )

    def run(
            self,
            user_query: Union[str, List[ContentBlock]],
            stream: bool = False,
            tts: str = "default",
            available_tools: Optional[List[str]] = None,
    ) -> Iterator[AgentEvent]:
        """
        Run the agent loop

        Args:
            user_query: User's query (text string or list of content blocks for multimodal)
            stream: Whether to stream LLM responses

        Yields:
            AgentEvent objects representing agent progress
        """
        # 1. Add user message to context
        self.context_engine.add_user_message(user_query)

        # 2. Log the user query using helper method
        query_summary = self._summarize_query(user_query)
        mainLogger.info(
            "Starting user query",
            session_id=self.session_id,
            prompt_id=self.context_engine.prompt_id,
            query_summary=query_summary
        )

        if self.metrics_collector:
            prompt_tracker_ctx = self.metrics_collector.track_prompt(user_query)
            prompt_tracker = prompt_tracker_ctx.__enter__()
        else:
            prompt_tracker_ctx = None
            prompt_tracker = None

        try:
            tts_processor = tts_registry.get_processor(tts)

            if tts_processor is None:
                yield AgentEvent(
                    type="error",
                    data={"error": f"tts mode '{tts}' not supported"}
                )
                return

            # Create TTS context
            tts_context = TTSContext(
                llm=self.llm,
                tool_registry=self.tool_registry,
                context_engine=self.context_engine,
                max_iterations=self.max_iterations,
                yolo_mode=self.yolo_mode,
                confirmation_callback=self.confirmation_callback,
                metrics_collector=self.metrics_collector,
                available_tools=available_tools,
                stream=stream,
                prompt_tracker=prompt_tracker,
                branches_file=self.branches_file,
            )

            # Process using the selected TTS processor
            yield from tts_processor.process(tts_context)

        finally:
            # Close prompt tracker context
            if prompt_tracker_ctx:
                prompt_tracker_ctx.__exit__(None, None, None)
