from typing import Iterator, Any

from codefuse.core.utils_tts import _handle_streaming_llm
from codefuse.observability import mainLogger

from codefuse.core import ToolExecutor
from codefuse.core.tts_processor import BaseTTSProcessor, TTSContext
from codefuse.core.agent_loop import AgentEvent




class DefaultTTSProcessor(BaseTTSProcessor):
    """Default TTS processor - standard iterative approach"""

    @property
    def name(self) -> str:
        return "default"

    def process(self, context: TTSContext) -> Iterator[Any]:
        """Process using the default iterative approach"""
        # Import here to avoid circular imports

        iteration = 0
        final_response = ""

        # Create tool executor for this processing context
        tool_executor = ToolExecutor(
            tool_registry=context.tool_registry,
            context_engine=context.context_engine,
            yolo_mode=context.yolo_mode,
            confirmation_callback=context.confirmation_callback,
            metrics_collector=context.metrics_collector,
        )
        mainLogger.info(
            "进入普通",
            iteration=iteration,
            max_iterations=context.max_iterations,
            session_id=context.context_engine.session_id,
        )

        while iteration < context.max_iterations:
            iteration += 1
            mainLogger.info(
                "Agent iteration",
                iteration=iteration,
                max_iterations=context.max_iterations,
                session_id=context.context_engine.session_id,
            )

            # Track iteration in metrics
            if context.prompt_tracker:
                context.prompt_tracker.increment_iteration()

            # Get current messages and tools from context engine
            messages = context.context_engine.get_messages_for_llm()
            tools = context.context_engine.get_tools_for_llm()

            try:
                # Call LLM
                yield AgentEvent(
                    type="llm_start",
                    data={
                        "iteration": iteration,
                        "session_id": context.context_engine.session_id,
                    }
                )

                if context.stream:
                    # Streaming mode - yield events directly
                    llm_response = yield from _handle_streaming_llm(
                        llm=context.llm,
                        messages=messages,
                        tools=tools,
                        session_id=context.context_engine.session_id,
                        metrics_collector=context.metrics_collector,
                    )

                else:
                    # Non-streaming mode - track with metrics
                    if context.metrics_collector:
                        with context.metrics_collector.track_api_call() as api_tracker:
                            llm_response = context.llm.generate(
                                messages=messages,
                                tools=tools,
                                stream=False,
                            )

                            # Record token usage if available
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
                    else:
                        llm_response = context.llm.generate(
                            messages=messages,
                            tools=tools,
                            stream=False,
                        )

                    yield AgentEvent(
                        type="llm_done",
                        data={
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
                            "session_id": context.context_engine.session_id,
                        }
                    )

                # Add assistant message to context engine
                # This automatically writes to trajectory with iteration number
                context.context_engine.add_assistant_message(llm_response, iteration=iteration)

                # Write LLM messages snapshot after each assistant response
                context.context_engine.write_llm_messages(context.llm)

                # Check if we have tool calls
                if not llm_response.has_tool_calls:
                    # No tool calls - we're done
                    final_response = llm_response.content
                    break

                # Execute tool calls
                for tool_call in llm_response.tool_calls:
                    result_events = tool_executor.execute_tool_call(
                        tool_call,
                        session_id=context.context_engine.session_id,
                    )
                    # Convert ToolExecutionEvent to AgentEvent
                    for tool_event in result_events:
                        yield AgentEvent(type=tool_event.type, data=tool_event.data)

                # Continue to next iteration

            except Exception as e:
                mainLogger.error(
                    "Error in agent loop iteration",
                    iteration=iteration,
                    error=str(e),
                    session_id=context.context_engine.session_id,
                    exc_info=True,
                )
                yield AgentEvent(
                    type="error",
                    data={"error": str(e), "iteration": iteration}
                )
                break

        # Check if we hit max iterations
        if iteration >= context.max_iterations and not final_response:
            final_response = "Maximum iterations reached. The task may not be complete."
            mainLogger.warning(
                "Agent loop reached maximum iterations",
                iterations=iteration,
                session_id=context.context_engine.session_id,
            )

        # Write final LLM messages snapshot (ensure last response is captured)
        context.context_engine.write_llm_messages(context.llm)

        # Send final done event
        yield AgentEvent(
            type="agent_done",
            data={
                "final_response": final_response,
                "iterations": iteration,
                "session_id": context.context_engine.session_id,
            }
        )

