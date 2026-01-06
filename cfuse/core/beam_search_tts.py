import json
import re
import uuid
from datetime import datetime, timezone
from typing import Iterator, List, Any, Dict, Optional, Tuple
import concurrent.futures

from cfuse.core.utils_tts import BeamPath
from cfuse.llm.base import MessageRole, Message, ToolCall
from cfuse.observability import mainLogger

from cfuse.core import ToolExecutor
from cfuse.core.tts_processor import BaseTTSProcessor, TTSContext
from cfuse.core.agent_loop import AgentEvent
from pathlib import Path
from cfuse.observability.logging.setup import setup_logging
from egss.dss.tts.git_tree.config.settings import GitTreeConfig
from egss.dss.tts.git_tree.managers.git_tree_manager_simplified import \
    GitTreeManagerSimplified as GitTreeManager


class BeamSearchTTSProcessor(BaseTTSProcessor):
    """Beam Search TTS processor - beam search approach for exploring multiple solution paths"""

    def __init__(self, git_tree_manager: Optional['GitTreeManager'] = None, concurrent_mode: bool = True, judge_llm=None):
        super().__init__()
        self.git_tree_manager = git_tree_manager
        self._git_tree_manager_initialized = git_tree_manager is not None
        self.concurrent_mode = concurrent_mode
        self.judge_llm = judge_llm

    def _ensure_git_tree_manager(self, context: TTSContext) -> 'GitTreeManager':
        """Ensure git_tree_manager is initialized, create it based on configuration if not"""
        if self.git_tree_manager is None:
            base_workspace = context.context_engine.workspace

            # Use the same session directory structure as evaluation records
            session_dir = setup_logging(
                session_id=context.context_engine.session_id,
                workspace_path=base_workspace
            )

            # Create beam_search directory under session directory
            name = base_workspace.split("/")[-1]
            diff_workspace = session_dir / "beam_search" / name
            diff_workspace.mkdir(parents=True, exist_ok=True)
            max_workspaces = 2

            git_config = GitTreeConfig(
                diff_workspace=Path(diff_workspace),
                base_workspace=base_workspace,
                max_workspaces=max_workspaces
            )
            self.git_tree_manager = GitTreeManager(git_config)
            self._git_tree_manager_initialized = True

        return self.git_tree_manager

    @property
    def name(self) -> str:
        return "beam_search"

    def _single_llm_call(self, context: TTSContext, messages: List[Any], tools: List[Any]) -> Any:
        """Single LLM call"""
        return self._single_llm_call_with_llm(context, messages, tools, context.llm)

    def _single_llm_call_with_llm(self, context: TTSContext, messages: List[Any], tools: List[Any], llm) -> Any:
        """Single call using specified LLM"""
        if context.metrics_collector:
            with context.metrics_collector.track_api_call() as api_tracker:
                response = llm.generate(
                    messages=messages,
                    tools=tools,
                    stream=False,
                )

                # Record token usage if available
                if response.usage:
                    api_tracker.set_tokens(
                        prompt_tokens=response.usage.prompt_tokens,
                        completion_tokens=response.usage.completion_tokens,
                        total_tokens=response.usage.total_tokens,
                        cache_creation_tokens=response.usage.cache_creation_input_tokens,
                        cache_read_tokens=response.usage.cache_read_input_tokens,
                    )

                if response.model:
                    api_tracker.set_model(response.model)

                if response.finish_reason:
                    api_tracker.set_finish_reason(response.finish_reason)

                return response
        else:
            return llm.generate(
                messages=messages,
                tools=tools,
                stream=False,
            )

    def _generate_multiple_responses(self, context: TTSContext, messages: List[Any], tools: List[Any],count: int = 4) -> List[Any]:
        """Generate multiple LLM responses, supporting both concurrent and synchronous modes"""
        responses = []

        if self.concurrent_mode:
            print("Concurrent mode: Using thread pool for concurrent LLM calls")
            # Use thread pool for concurrent LLM calls
            with concurrent.futures.ThreadPoolExecutor(max_workers=count) as executor:
                futures = [executor.submit(self._single_llm_call, context, messages, tools) for _ in range(count)]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        response = future.result()
                        responses.append(response)
                    except Exception as e:
                        mainLogger.error(
                            "Error generating response in parallel",
                            error=str(e),
                            session_id=context.context_engine.session_id,
                            exc_info=True,
                        )
        else:
            # Synchronous mode: Execute LLM calls sequentially
            print("Synchronous mode: Execute LLM calls sequentially")
            for i in range(count):
                try:
                    response = self._single_llm_call(context, messages, tools)
                    responses.append(response)
                except Exception as e:
                    mainLogger.error(
                        "Error generating response synchronously",
                        error=str(e),
                        session_id=context.context_engine.session_id,
                        exc_info=True,
                    )

        return responses

    def _initialize_beam(self, initial_messages: List[Dict[str, Any]], run_space: Path) -> List[BeamPath]:
        """Initialize the root path of the beam"""
        root_path = BeamPath(
            path_id="root",
            messages=[item.copy() for item in initial_messages],
            score=1.0,
            is_stopped="continue",
            step=0,
            run_workspace=run_space,
            parent_path_id=None,
            parent_commit_id=None,
            history=[item.copy() for item in initial_messages]
        )
        # Create initial commit
        initial_commit = self.git_tree_manager.create_commit(
            message="Initial state",
            parent_commit_id=None,
            step=0,
            chat_history=initial_messages,
            is_stopped="continue"
        )
        root_path.commit_id = initial_commit

        return [root_path]

    def _dict_to_messages(self, messages_dict: List[Dict[str, Any]]) -> List[Message]:
        """Convert dictionary format messages to Message object list"""
        messages = []
        for message_dict in messages_dict:
            tool_calls = None
            if message_dict.get("tool_calls"):
                tool_calls = []
                for tc_dict in message_dict["tool_calls"]:
                    if isinstance(tc_dict, dict):
                        tool_calls.append(ToolCall(
                            id=tc_dict["id"],
                            type=tc_dict["type"],
                            function=tc_dict["function"]
                        ))
                    else:
                        tool_calls.append(tc_dict)

            message = Message(
                role=MessageRole(message_dict["role"]),
                content=message_dict["content"],
                name=message_dict.get("name"),
                tool_calls=tool_calls,
                tool_call_id=message_dict.get("tool_call_id")
            )
            messages.append(message)
        return messages

    def _generate_candidates_for_path(self, context: TTSContext, path: BeamPath, beam_width: int, step: int) -> List[BeamPath]:
        """Generate candidate responses for a single path"""
        messages_dict = path.messages
        tools = context.context_engine.get_tools_for_llm()
        candidates = []
        # Convert messages to Message objects
        messages = self._dict_to_messages(messages_dict)


        responses = self._generate_multiple_responses(context, messages, tools, count=beam_width)
        signatures = []
        for response in responses:
            if response.has_tool_calls and response.tool_calls:
                signature = [tc.function["name"] for tc in response.tool_calls]
                signatures.extend(signature)
            else:
                print("no tool_calls")

        if "write_file" in signatures or "edit_file" in signatures:
            print("write_file or edit_file")
        else:
            print("no write_file or edit_file")
        # Use extracted method to create new BeamPath
        new_paths = []
        for idx, response in enumerate(responses):
            candidate = {
                "index": idx,
                "response": response,
                "path": path
            }
            candidates.append(candidate)
        all_candidates = self._deduplicate_candidates(candidates, context, step)
        for candidate in all_candidates:
            new_path = self._create_beam_path_from_candidate(candidate, score=0)
            new_paths.append(new_path)
        return new_paths

    def _create_beam_path_from_candidate(self, candidate: Dict[str, Any], score: float) -> BeamPath:
        """Create new BeamPath from candidate response"""
        response = candidate["response"]
        path = candidate["path"]

        # Create new message history
        new_messages = [item.copy() for item in path.messages]

        # Add assistant message
        tool_calls = []
        if response.has_tool_calls:
            for tc in response.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "type": tc.type,
                    "function": tc.function,
                })

        assistant_msg = {
            "role": "assistant",
            "content": response.content,
            "tool_calls": tool_calls,
            "request_id": str(uuid.uuid4())
        }
        new_messages.append(assistant_msg)

        # Create new path
        new_path_id = f"{path.path_id}_c{candidate['index']}"
        new_path = BeamPath(
            path_id=new_path_id,
            messages=new_messages,
            is_stopped="continue" if response.has_tool_calls else "stop",
            step=path.step + 1,
            run_workspace=path.run_workspace,
            parent_path_id=path.path_id,
            parent_commit_id=path.commit_id,
            response=candidate["response"],
            score=score,
            compression_history=path.compression_history.copy()
        )
        return new_path

    def _check_token_length_and_log(self, context: TTSContext, prompt: str, max_token_threshold: int = 30000) -> bool:
        """Check if token length exceeds threshold and write to log file

        Args:
            context: TTS context
            prompt: Prompt text to check
            max_token_threshold: Token length threshold, default 8000

        Returns:
            bool: True if exceeds threshold, False otherwise
        """
        # Simple token estimation (Chinese characters ≈ 2 tokens, English characters ≈ 0.25 tokens)
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', prompt))
        english_chars = len(re.findall(r'[a-zA-Z]', prompt))
        estimated_tokens = chinese_chars * 2 + english_chars * 0.25 + len(prompt) * 0.1

        if estimated_tokens > max_token_threshold:
            # Create log record
            log_entry = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'event_type': 'token_length_exceeded',
                'session_id': context.context_engine.session_id,
                'estimated_tokens': estimated_tokens,
                'max_threshold': max_token_threshold,
                'prompt_length': len(prompt),
                'prompt': prompt
            }

            # Ensure log directory exists
            log_dir = self.git_tree_manager.config.judge_path
            log_dir.mkdir(parents=True, exist_ok=True)

            # Write to log file, following judge_message.json format
            log_file = log_dir / "token_length_warnings.jsonl"
            with open(log_file, 'a', encoding='utf-8') as f:
                json_line = json.dumps(log_entry, ensure_ascii=False)
                f.write(json_line + '\n')

            mainLogger.warning(
                "Token length exceeded threshold",
                estimated_tokens=estimated_tokens,
                max_threshold=max_token_threshold,
                session_id=context.context_engine.session_id
            )
            return True
        return False

    def _format_messages_to_trajectory(self, messages: List[Dict[str, Any]],  compress_mode="large") -> Tuple[str, str]:
        trajectory_language_format = ""
        task = ""
        tool_name = ""
        for msg_idx in range(len(messages)):
            mes = messages[msg_idx]
            if mes.get("role") == MessageRole.USER:
                task = mes.get("content", "")
            elif mes.get("role") == MessageRole.ASSISTANT:
                tool_calls = mes.get("tool_calls") or []
                for tool_call in tool_calls:
                    if isinstance(tool_call, dict):
                        tool_name = tool_call.get("function", {}).get("name", "")
                        arguments = tool_call.get("function", {}).get("arguments", "")
            elif mes.get("role") == MessageRole.TOOL:
                content = mes.get("content", "")
                if tool_name == "read_file" or tool_name == "grep" or tool_name == "glob":
                    if compress_mode == "large":
                        content = content[:200]
                    elif compress_mode == "middle":
                        content = content[:100]
                    elif compress_mode == "small":
                        content = content[:50]

                elif tool_name == "write_file" or tool_name == "bash":
                    content = content[:500]

                trajectory_language_format += f"""
<tool_call name="{tool_name}">
    <arguments>
    {arguments}
    "content": "{content}"
    </arguments>
</tool_call>
"""

        return trajectory_language_format, task

    def _evaluate_and_select_best_paths(self, context: TTSContext, all_candidates_paths: List[BeamPath],
                                        beam_k: int) -> List[BeamPath]:
        """Evaluate candidates and select best paths"""
        if not all_candidates_paths:
            return []

        return self._evaluate_and_select_best_paths_concurrent(context, all_candidates_paths, beam_k)

    def _evaluate_and_select_best_paths_concurrent(self, context: TTSContext, all_candidates_paths: List[BeamPath],
                                                   beam_k: int) -> List[BeamPath]:
        """Concurrent version: Evaluate candidates and select best paths"""
        if not all_candidates_paths:
            return []

        # Use thread pool for concurrent evaluation of candidates
        max_workers = min(len(all_candidates_paths), 10)  # Limit maximum concurrency

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all evaluation tasks
            future_to_candidate = {
                executor.submit(self._evaluate_single_candidate, context, candidate_path, idx):
                    (candidate_path, idx)
                for idx, candidate_path in enumerate(all_candidates_paths)
            }

            # Collect results
            scored_candidates = []
            judge_responses = []
            judge_message = []
            compression_records = []

            for future in concurrent.futures.as_completed(future_to_candidate):
                candidate_path, idx = future_to_candidate[future]
                try:
                    result = future.result()
                    if result:
                        scored_candidates.append({
                            "candidate": result["candidate"],
                            "score": result["score"]
                        })
                        judge_responses.extend(result.get("judge_responses", []))
                        if result.get("judge_message"):
                            judge_message.extend(result["judge_message"])
                        compression_records.extend(result.get("compression_records", []))
                except Exception as e:
                    mainLogger.warning(
                        "Failed to evaluate candidate in concurrent execution",
                        error=str(e),
                        candidate_index=idx,
                        session_id=context.context_engine.session_id
                    )
                    # Give base score on failure
                    scored_candidates.append({
                        "candidate": candidate_path,
                        "score": 0.5
                    })

        return self._process_scored_candidates(context, scored_candidates, judge_responses, judge_message,
                                               compression_records, beam_k)

    def _evaluate_single_candidate(self, context: TTSContext, candidate_path: BeamPath, candidate_index: int,
                                   tts_entropy=None) -> Dict[str, Any]:
        """Evaluate a single candidate path"""
        response = candidate_path.response
        path = candidate_path
        compression_records = []

        # Give base score if no tool calls
        if not response.has_tool_calls:
            mainLogger.info(
                "No tool calls",
                max_iterations=context.max_iterations,
                session_id=context.context_engine.session_id,
                candidate_index=candidate_index
            )
            return {
                "candidate": candidate_path,
                "score": 0,
                "judge_responses": [],
                "judge_message": [],
                "compression_records": []
            }

        # Use judge function for evaluation
        try:
            messages = path.messages
            trajectory_language_format, task = self._format_messages_to_trajectory(messages[:-1])
            tool_language_format = ""
            for tool_call in response.tool_calls:
                name = tool_call.function["name"]
                arguments = tool_call.function["arguments"]
                tool_language_format += f"""
<tool_call name="{name}">\n 
    <arguments>
    {arguments}
    "content": "{response.content}"
    </arguments>
</tool_call>
"""
            # Record original prompt before compression
            original_trajectory = trajectory_language_format
            if original_trajectory == "":
                original_trajectory = "empty"
            original_prompt = tts_entropy.format(trajectory=original_trajectory, task=task, response=tool_language_format)

            chinese_char_count = len(re.findall(r'[\u4e00-\u9fff]', original_prompt))
            non_chinese_char_count = len(original_prompt) - chinese_char_count
            original_token_count = chinese_char_count + (non_chinese_char_count / 4)
            mainLogger.warning("Using character-based token estimation", estimated_tokens=int(original_token_count))
            if original_token_count > 30000:
                trajectory_language_format, task = self._format_messages_to_trajectory(messages[:-1],
                                                                                       compress_mode="large")
            elif original_token_count > 20000 and original_token_count <= 30000:
                trajectory_language_format, task = self._format_messages_to_trajectory(messages[:-1],
                                                                                       compress_mode="middle")
            elif original_token_count > 12000 and original_token_count <= 20000:
                trajectory_language_format, task = self._format_messages_to_trajectory(messages[:-1],
                                                                                       compress_mode="small")
            final_prompt = tts_entropy.format(trajectory=original_trajectory, task=task,
                                               response=tool_language_format)

            chinese_char_count = len(re.findall(r'[\u4e00-\u9fff]', final_prompt))
            non_chinese_char_count = len(final_prompt) - chinese_char_count
            final_prompt_1 = chinese_char_count + (non_chinese_char_count / 4)
            mainLogger.warning("compressed Using character-based token estimation", estimated_tokens=int(final_prompt_1))
            # Record compression information
            compression_records.append({
                'candidate_index': candidate_index,
                'step': candidate_path.step,
                'target_tools': ['glob', 'grep', 'read_file'],
                'original_prompt': original_prompt,
                'compressed_prompt': final_prompt,
                'original_length': len(original_prompt),
                'compressed_length': len(final_prompt),
                'compression_ratio': len(final_prompt) / len(original_prompt) if len(
                    original_prompt) > 0 else 1.0
            })

            # Check token length and log
            self._check_token_length_and_log(context, final_prompt)
            judge_message = [Message(MessageRole.USER, content=final_prompt, name="judge")]
            judge_llm = self.judge_llm if self.judge_llm is not None else context.llm
            judge_response = self._single_llm_call_with_llm(context, judge_message, tools=[], llm=judge_llm)

            # Parse score
            content = judge_response.content
            match = re.search(r'```json\s*({.*?})\s*```', content, re.DOTALL)
            if match:
                json_str = match.group(1)
                data = json.loads(json_str)
                score_str = str(data.get("scalar", "0"))
                if "/" in score_str:
                    try:
                        numerator, denominator = score_str.split("/")
                        score = float(numerator) / float(denominator)
                    except (ValueError, ZeroDivisionError):
                        score = 0.5
                else:
                    score = float(score_str)
            else:
                data = "Error occurred"
                score_str = "0"
                score = 0

            return {
                "candidate": candidate_path,
                "score": score,
                "judge_responses": [{"response": data if match else content, "score": score_str if match else "0.5"}],
                "judge_message": judge_message,
                "compression_records": compression_records
            }

        except Exception as e:
            mainLogger.warning(
                "Failed to evaluate candidate",
                error=str(e),
                candidate_index=candidate_index,
                session_id=context.context_engine.session_id
            )
            return {
                "candidate": candidate_path,
                "score": 0,
                "judge_responses": [],
                "judge_message": [],
                "compression_records": []
            }

    def _process_scored_candidates(self, context: TTSContext, scored_candidates: List[Dict[str, Any]],
                                   judge_responses: List[Dict[str, Any]], judge_message: List[Message],
                                   compression_records: List[Dict[str, Any]], beam_k: int) -> List[BeamPath]:
        """Process evaluation results and select best paths"""
        # Sort by score and select top beam_k
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        selected_candidates = scored_candidates[:beam_k]

        # Ensure git_tree_manager is initialized to get judge_path
        judge_path = self.git_tree_manager.config.judge_path
        judge_path.mkdir(parents=True, exist_ok=True)

        # Create evaluation writer
        session_id = context.context_engine.session_id
        # Prepare evaluation data
        candidate_responses_data = []

        for idx, item in enumerate(scored_candidates):
            candidate = item["candidate"]
            response = candidate.response
            score = item["score"]

            candidate_responses_data.append({
                'index': idx,
                'content': response.content,
                'tool_calls': [
                    {
                        'id': tc.id,
                        'type': tc.type,
                        'function': tc.function
                    } for tc in (response.tool_calls or [])
                ],
                'has_tool_calls': response.has_tool_calls,
                'score': score
            })
        judge_message_data = []
        for mes in judge_message:
            judge_message_data.append({
                'role': mes.role,
                'content': mes.content,
                'name': mes.name
            })

        # Save evaluation records - use custom format supporting multiple selected indices
        evaluation_event = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'event_type': 'beam_search_judge_evaluation',
            'session_id': session_id,
            "input": judge_message_data,
            'candidate_count': len(candidate_responses_data),
            'selected_indices': list(range(len(selected_candidates))),
            'candidate_responses': candidate_responses_data,
            'judge_responses': judge_responses,
            'compression_records': compression_records,
            'evaluation_criteria': {
                'beam_k': beam_k,
                'total_candidates': len(scored_candidates),
                'selection_method': 'highest_score',
                'step': len(selected_candidates)
            }
        }

        # Write evaluation file
        judge_file = judge_path / f"beam_judge_{len(selected_candidates)}.jsonl"
        with open(judge_file, 'a', encoding='utf-8') as f:
            json_line = json.dumps(evaluation_event, ensure_ascii=False)
            f.write(json_line + '\n')
        candidates = []
        for idx, item in enumerate(selected_candidates):
            candidate = item["candidate"]
            candidate.score = item["score"]
            candidates.append(candidate)

        return candidates

    def _execute_tool_calls_for_path(self, context: TTSContext, path: BeamPath, index: int):
        """Execute tool calls for a path"""
        # Switch to corresponding branch
        if path.parent_commit_id:
            self.git_tree_manager.checkout_to_commit(path.parent_commit_id)
            new_commit_id = self.git_tree_manager._create_branch_and_commit(path.parent_commit_id, path.step, index)
            path.commit_id = new_commit_id


        tool_executor = ToolExecutor(
            tool_registry=context.tool_registry,
            context_engine=context.context_engine,
            yolo_mode=context.yolo_mode,
            confirmation_callback=context.confirmation_callback,
            metrics_collector=context.metrics_collector,
        )

        # Get tool calls from last message
        last_message = path.messages[-1]
        if isinstance(last_message, dict) and "tool_calls" in last_message and last_message["tool_calls"]:
            # Checkout to current path's commit state, ensure tools execute on correct branch
            for tool_call_data in last_message["tool_calls"]:
                tool_call = ToolCall(
                    id=tool_call_data["id"],
                    type=tool_call_data["type"],
                    function=tool_call_data["function"]
                )
                result_events = tool_executor.execute_tool_call(
                    tool_call,
                    session_id=context.context_engine.session_id,
                )
                # Add tool results to message history
                for tool_event in result_events:
                    if tool_event.type == "tool_done":
                        tool_result_msg = {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": str(tool_event.data.get("result", "")),
                            "request_id": str(uuid.uuid4())
                        }
                        path.messages.append(tool_result_msg)
            # Create git commit (commit on existing branch, don't create new branch)
            commit_message = f"Step {path.step} index {index} candidate {path.path_id}"
            self.git_tree_manager.commit_to_existing_branch(
                message=commit_message,
                commit_id=path.commit_id,
                parent_commit_id=path.parent_commit_id,
                step=path.step,
                chat_history=path.messages,
                is_stopped=path.is_stopped
            )
            path.history = path.messages

    def _deduplicate_candidates(self, candidates: List[Dict[str, Any]], context: TTSContext, step: int) -> List[Dict[str, Any]]:
        if not candidates:
            return candidates

        original_count = len(candidates)
        seen_signatures = set()
        unique_candidates = []

        def _get_tool_signature(tool_call) -> str:
            """Generate unique signature for tool call, including function name and all parameters"""
            func_name = tool_call.function["name"]
            try:
                args = json.loads(tool_call.functionarguments)
                if func_name == "edit_file":
                    file_path = args.get("file_path", "")
                    old_string = args.get("old_string", "")
                    new_string = args.get("new_string", "")
                    replace_all = args.get("replace_all", False)
                    return f"edit_file:{file_path}:{hash(old_string)}:{hash(new_string)}:{replace_all}"
                elif func_name == "glob":
                    pattern = args.get("pattern", "")
                    path = args.get("path", "")
                    return f"glob:{pattern}:{path}"
                elif func_name == "grep":
                    pattern = args.get("pattern", "")
                    path = args.get("path", "")
                    glob_pattern = args.get("glob", "")
                    output_mode = args.get("output_mode", "files_with_matches")
                    return f"grep:{pattern}:{path}:{glob_pattern}:{output_mode}"
                elif func_name == "read_file":
                    path = args.get("path", "")
                    start_line = args.get("start_line", "")
                    end_line = args.get("end_line", "")
                    return f"read_file:{path}:{start_line}:{end_line}"
                elif func_name == "write_file":
                    path = args.get("path", "")
                    content = args.get("content", "")
                    return f"write_file:{path}:{hash(content)}"
                else:
                    args_str = ",".join([f"{k}={v}" for k, v in sorted(args.items())])
                    return f"{func_name}:{args_str}"
            except (json.JSONDecodeError, AttributeError):
                return f"{func_name}:invalid_args"

        for candidate in candidates:
            response = candidate["response"]
            if not response.has_tool_calls:
                content = response.content.strip()
                signature = f"content:{hash(content)}"
            else:
                tool_signatures = []
                for tool_call in response.tool_calls:
                    tool_signature = _get_tool_signature(tool_call)
                    tool_signatures.append(tool_signature)
                tool_signatures.sort()
                signature = "|".join(tool_signatures)

            if signature not in seen_signatures:
                seen_signatures.add(signature)
                unique_candidates.append(candidate)

        if len(unique_candidates) < original_count:
            mainLogger.info(
                "removed duplicates",
                original_count=original_count,
                unique_count=len(unique_candidates),
                duplicates_removed=original_count - len(unique_candidates),
                session_id=context.context_engine.session_id,
                step=step
            )

        return unique_candidates

    def _save_step_state(self, context: TTSContext, step: int, phase: str, paths: List[BeamPath]):
        state = {
            "step": step,
            "phase": phase,
            "current_beam_size": len(paths),
            "paths": []
        }
        for path in paths:
            commit_info = self.git_tree_manager.get_commit_info(path.commit_id)
            if commit_info:
                state["paths"].append({
                    "path_id": path.path_id,
                    "parent_commit_id": path.parent_commit_id,
                    "score": path.score,
                    "is_stopped": path.is_stopped,
                    "commit_id": path.commit_id,
                    "step_index": path.step,
                    "message": commit_info.get("message"),
                    "run_workspace": commit_info.get("run_workspace"),
                    "chat_history_path": commit_info.get("chat_history_path")
                })
            else:
                state["paths"].append({
                    "path_id": path.path_id,
                    "parent_commit_id": path.parent_commit_id,
                    "score": path.score,
                    "is_stopped": path.is_stopped,
                    "commit_id": path.commit_id,
                    "step_index": path.step
                })
        state_file = self.git_tree_manager.config.beam_path_infor / f"step_{step}_{phase}.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)

        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

        mainLogger.info(
            "save state",
            step=step,
            phase=phase,
            beam_size=len(paths),
            state_file=str(state_file),
            session_id=context.context_engine.session_id
        )


    def choose_beam(self, all_paths_history: list[BeamPath], beam_k) -> list[BeamPath]:
        """Select best paths"""
        if len(all_paths_history) <= beam_k:
            return all_paths_history
        else:
            max_depth = max([path.step for path in all_paths_history])
            total_step = max_depth
            a_penalty = 0.1
            step_penalty = 1 - ((a_penalty * total_step) / max(total_step, 1))
            for path in all_paths_history:
                base_score = path.score
                confidence = base_score * step_penalty
                path.score = confidence
            all_paths_history.sort(key=lambda x: x.score, reverse=True)
            return all_paths_history[:beam_k]

    def process(self, context: TTSContext, situation="online") -> Iterator[Any]:
        """Process using the beam search approach"""
        beam_width = 4  # Candidates generated per step
        beam_k = 4  # Best paths retained per step
        max_depth = min(context.max_iterations, 200)  # Maximum search depth

        mainLogger.info(
            "beam search",
            beam_width=beam_width,
            beam_k=beam_k,
            max_depth=max_depth,
            session_id=context.context_engine.session_id,
        )

        initial_messages = context.context_engine.get_messages_for_llm()
        initial_messages_dict = [msg.to_dict() for msg in initial_messages]
        self.git_tree_manager = self._ensure_git_tree_manager(context)
        run_space = self.git_tree_manager.workspace_manager.base_workspace
        self.git_tree_manager.cleanup_all_beam_branches()
        current_beam = self._initialize_beam(initial_messages_dict, run_space)

        all_paths_history = []
        all_paths = []
        self._save_step_state(context, 0, "initialized", current_beam)
        step = 0
        for step in range(max_depth):
            mainLogger.info(
                "Beam search step",
                step=step,
                beam_size=len(current_beam),
                session_id=context.context_engine.session_id,
            )
            for path in current_beam:
                all_paths.append(path)
                if path.is_stopped == "stop":
                    all_paths_history.append(path)
            active_paths = [path for path in current_beam if path.is_stopped == "continue"]
            if not active_paths:
                mainLogger.info(
                    "all paths stop",
                    session_id=context.context_engine.session_id,
                )
                break
            all_candidates_paths = []
            for path in active_paths:
                yield AgentEvent(
                    type="beam_search_path",
                    data={
                        "path_id": path.path_id,
                        "step": path.step,
                        "score": path.score,
                        "session_id": context.context_engine.session_id,
                    }
                )
                candidates_paths = self._generate_candidates_for_path(context, path, beam_width, step)
                all_candidates_paths.extend(candidates_paths)

            current_beam = self._evaluate_and_select_best_paths(context, all_candidates_paths, beam_k)

            index = 0
            for path in current_beam:
                context.context_engine.add_assistant_message(path.response, iteration=step)
                context.context_engine.write_llm_messages(context.llm)
                self._execute_tool_calls_for_path(context, path, index)
                index += 1
            self._save_step_state(context, step, "update", current_beam)

            if len(all_candidates_paths) >= 1:
                choose_beam_search = self.choose_beam(all_candidates_paths, beam_k)
            else:
                choose_beam_search = self.choose_beam(all_candidates_paths, beam_k)

            branches_file = context.branches_file or "/workspace/logs/branches.txt"
            # Ensure directory exists
            Path(branches_file).parent.mkdir(parents=True, exist_ok=True)
            with open(branches_file, 'w', encoding='utf-8') as f:
                for path in choose_beam_search:
                    if path.commit_id:
                        branch_name = path.commit_id
                        status = "active" if path.is_stopped == "continue" else "stopped"
                        f.write(f"{branch_name} # {status}, score: {path.score}\n")

        choose_beam_search = self.choose_beam(all_paths_history, beam_k)

        branches_file = context.branches_file or "/workspace/logs/branches.txt"
        # Ensure directory exists
        Path(branches_file).parent.mkdir(parents=True, exist_ok=True)
        with open(branches_file, 'w', encoding='utf-8') as f:
            for path in choose_beam_search:
                if path.commit_id:
                    branch_name = path.commit_id
                    status = "active" if path.is_stopped == "continue" else "stopped"
                    f.write(f"{branch_name} # {status}, score: {path.score}\n")


        yield AgentEvent(
            type="agent_done",
            data={
                "final_response": "final_response",
                "iterations": step + 1,
                "beam_size": len(all_paths_history),
                "active_beam_size": len(current_beam),
                "session_id": context.context_engine.session_id,
            }
        )
