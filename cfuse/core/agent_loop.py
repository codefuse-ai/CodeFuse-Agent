"""
Agent Loop - Main agent execution loop with tool calling
"""

from dataclasses import dataclass
from typing import Iterator, List, Optional, Literal, Any, Callable

from codefuse.config import Config
from codefuse.core.tts_processor import tts_registry, TTSContext
from codefuse.llm.base import BaseLLM, Message
from codefuse.tools.registry import ToolRegistry
from codefuse.core.context_engine import ContextEngine
from codefuse.core.environment import EnvironmentInfo
from codefuse.core.tool_executor import ToolExecutor
from codefuse.observability import MetricsCollector, mainLogger
from codefuse.core.agent_config import AgentProfile


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
        "beam_search_step_complete",  # Beam search step completed
        "beam_search_done",  # Beam search completed
        "beam_search_error",  # Beam search error
        "beam_search_path",  # Beam search path

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
            judge_llm: Optional[BaseLLM] = None,
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
            judge_llm: Optional judge LLM instance for beam search TTS
        """
        self.llm = llm
        self.tool_registry = tool_registry
        self.context_engine = context_engine
        self.max_iterations = max_iterations
        self.yolo_mode = yolo_mode
        self.confirmation_callback = confirmation_callback
        self.metrics_collector = metrics_collector
        self.judge_llm = judge_llm

        # Initialize tool executor
        self.tool_executor = ToolExecutor(
            tool_registry=tool_registry,
            context_engine=context_engine,
            yolo_mode=yolo_mode,
            confirmation_callback=confirmation_callback,
            metrics_collector=metrics_collector,
        )

        mainLogger.info(
            "AgentLoop initialized",
            session_id=self.session_id,
            max_iterations=max_iterations,
            yolo_mode=yolo_mode,
            temperature=llm.temperature if hasattr(llm, 'temperature') else None,
        )

    @property
    def session_id(self) -> str:
        """Get session ID from context engine"""
        return self.context_engine.session_id

    def run(
            self,
            config: Config,
            user_query: str,
            conversation_history: Optional[List[Message]] = None,
            environment: Optional[EnvironmentInfo] = None,
            agent_profile: Optional[AgentProfile] = None,
            available_tools: Optional[List[str]] = None,
            stream: bool = False,
            tts: str = "default",
    ) -> Iterator[AgentEvent]:
        """
        Run the agent loop

        Args:
            user_query: User's query
            conversation_history: Previous conversation messages
            environment: Environment information
            agent_profile: Agent profile
            available_tools: List of tool names to make available (None = all)
            stream: Whether to stream LLM responses

        Yields:
            AgentEvent objects representing agent progress
        """
        # Collect environment if not provided
        # if tts == "beam_search":
        #     self.git_tree_manager = self._ensure_git_tree_manager(context)
        #
        #     run_space = self.git_tree_manager.workspace_manager.run_dir
        #
        #     self.git_tree_manager.workspace_manager.copy_base_to_workspace(run_space)

        if environment is None:
            environment = EnvironmentInfo.collect()

        # Initialize context engine (first time only)
        if not self.context_engine._initialized:
            self.context_engine.initialize(
                environment=environment,
                tool_registry=self.tool_registry,
                agent_profile=agent_profile,
                conversation_history=conversation_history or [],
                available_tools=available_tools,
            )

            # Write session start event (first time only)
            tool_names = available_tools if available_tools else self.tool_registry.list_tool_names()
            self.context_engine.write_session_start(
                agent_name=agent_profile.name,
                model=self.llm.model,
                tools=tool_names,
            )

        # Add user message to context (this also generates a new prompt_id)
        # This automatically writes to trajectory
        self.context_engine.add_user_message(user_query)

        # Log the user query
        mainLogger.info("Starting user query", session_id=self.session_id, prompt_id=self.context_engine.prompt_id)

        # Track prompt if metrics collector is available
        if self.metrics_collector:
            prompt_tracker_ctx = self.metrics_collector.track_prompt(user_query)
            prompt_tracker = prompt_tracker_ctx.__enter__()
        else:
            prompt_tracker_ctx = None
            prompt_tracker = None

        try:

            # Get the appropriate TTS processor
            if tts == "beam_search" and self.judge_llm is not None:
                # 使用带judge_llm的beam search处理器
                from codefuse.core.beam_search_tts import BeamSearchTTSProcessor
                tts_processor = BeamSearchTTSProcessor(concurrent_mode=True, judge_llm=self.judge_llm)
            else:
                # 使用标准注册表获取处理器
                tts_processor = tts_registry.get_processor(tts)

            if tts_processor is None:
                yield AgentEvent(
                    type="error",
                    data={"error": f"tts mode '{tts}' not supported"}
                )
                return

            # Create TTS context
            tts_context = TTSContext(
                config=config,
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
            )

            # Process using the selected TTS processor
            yield from tts_processor.process(tts_context)

        finally:
            # Close prompt tracker context
            if prompt_tracker_ctx:
                prompt_tracker_ctx.__exit__(None, None, None)
