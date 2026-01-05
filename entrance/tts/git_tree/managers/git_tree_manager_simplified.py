"""GitTree主管理器 - 基于Git分支的简化实现"""
import json
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

from entrance.tts.git_tree.managers.workspace_manager import WorkspaceManager

from ..models.node import GitTreeNode
from ..config.settings import GitTreeConfig
from ..managers.tree_storage import TreeStorageManager
from ..utils.id_generator import IDGenerator

logger = logging.getLogger(__name__)


class GitTreeManagerSimplified:
    """GitTree主管理器，使用Git分支简化实现"""

    def __init__(self, config: GitTreeConfig):
        """初始化GitTree管理器"""
        self.config = config
        self.storage_manager = TreeStorageManager(config)
        self.base_workspace = config.base_workspace
        self.run = config.run_dir

        self.workspace_manager = WorkspaceManager(config.run_dir, config.base_workspace, config.max_workspaces)

        # 获取当前分支名和主分支名
        self.current_branch = self._get_current_branch()
        self.main_branch = self._get_main_branch()

        logger.info(f"初始化GitTree管理器，基准工作空间: {config.base_workspace}")
        logger.info(f"当前分支: {self.current_branch}, 主分支: {self.main_branch}")

    def _get_current_branch(self) -> str:
        """获取当前分支名"""
        try:
            return self._run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
        except subprocess.CalledProcessError:
            print("无法获取当前分支名，使用默认值")
            return "master"

    def _get_main_branch(self) -> str:
        """获取主分支名，直接使用当前分支名"""
        return self.current_branch

    def _run_git_command(self, cmd: List[str], cwd: Optional[Path] = None, max_retries: int = 3) -> str:
        """运行Git命令，包含锁文件处理和重试机制"""
        if cwd is None:
            cwd = self.base_workspace
            
        # 重试机制
        for attempt in range(max_retries):
            try:
                # 在每次重试前确保Git仓库就绪
                self._ensure_git_ready(cwd)
                
                result = subprocess.run(
                    ["git"] + cmd,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    check=True
                )
                return result.stdout.strip()
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.strip()
                logger.error(f"Git命令失败 (尝试 {attempt + 1}/{max_retries}): {' '.join(cmd)}, 错误: {error_msg}")
                
                # 检查是否是锁文件相关的错误
                if any(keyword in error_msg.lower() for keyword in ["index.lock", "file exists", "lock file"]):
                    if attempt < max_retries - 1:
                        logger.warning(f"检测到锁文件问题，正在清理并重试...")
                        # 强制清理所有可能的锁文件
                        self._cleanup_lock_files_silent(cwd)
                        
                        # 等待一小段时间再重试
                        import time
                        time.sleep(0.5 * (attempt + 1))  # 指数退避
                        continue
                
                # 非锁文件错误或重试次数用完
                raise
        
        raise RuntimeError(f"Git命令在 {max_retries} 次尝试后仍然失败: {' '.join(cmd)}")

    def _cleanup_lock_files_silent(self, cwd: Optional[Path] = None) -> None:
        """静默清理所有Git锁文件，不抛出异常"""
        if cwd is None:
            cwd = self.base_workspace
        else:
            # 确保cwd是Path对象
            cwd = Path(cwd)
            
        git_dir = cwd / '.git'
        lock_files = [
            git_dir / 'index.lock',
            git_dir / 'refs' / 'heads.lock',
            git_dir / 'packed-refs.lock',
            git_dir / 'config.lock',
            git_dir / 'shallow.lock',
            git_dir / 'HEAD.lock'
        ]
        
        for lock_file in lock_files:
            if lock_file.exists():
                try:
                    lock_file.unlink()
                    logger.debug(f"静默清理锁文件: {lock_file}")
                except (OSError, PermissionError):
                    pass  # 静默忽略清理失败

    def _ensure_git_ready(self, cwd: Optional[Path] = None) -> None:
        """确保Git仓库处于可用状态"""
        if cwd is None:
            cwd = self.base_workspace
        else:
            # 确保cwd是Path对象
            cwd = Path(cwd)
            
        # 清理所有可能的锁文件
        self._cleanup_lock_files_silent(cwd)
        
        # 检查Git状态，确保仓库可用（使用直接的subprocess调用避免递归）
        try:
            import subprocess
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Git仓库状态异常: {e}")
            raise

    def _create_branch(self, commit_id: str, parent_commit_id: Optional[str] = None) -> None:
        """
        创建新的Git分支
        
        Args:
            commit_id: 新分支名（提交ID）
            parent_commit_id: 父提交ID，如果为None则基于主分支
        """
        # 确保Git仓库就绪
        self._ensure_git_ready()
        
        if parent_commit_id:
            # 检出到父分支
            self._run_git_command(["checkout", parent_commit_id])
            logger.info(f"检出到父分支: {parent_commit_id}")
        else:
            # 根节点，检出到主分支
            self._run_git_command(["checkout", self.main_branch])
            logger.info(f"检出到主分支: {self.main_branch}")

        # 创建新分支
        self._run_git_command(["checkout", "-b", commit_id])
        logger.info(f"创建新分支: {commit_id}")

    def _commit_changes(self, message: str) -> bool:
        """
        提交工作区更改
        
        Args:
            message: 提交消息
            
        Returns:
            是否成功提交（如果有更改则为True，无更改则为False）
        """
        try:
            # 确保Git仓库就绪
            self._ensure_git_ready()
            
            # 检查工作区是否有更改
            status_result = self._run_git_command(["status", "--porcelain"])
            if status_result.strip():
                # 有更改，执行提交
                self._run_git_command(["add", "."])
                self._run_git_command(["commit", "-m", message])
                logger.info(f"提交更改: {message}")
                return True
            else:
                # 没有更改，跳过提交
                logger.info("工作区没有更改，跳过提交")
                return False
        except subprocess.CalledProcessError as e:
            logger.warning(f"提交时发生错误: {e}")
            return False

    def _save_chat_history(self, commit_id: str, chat_history: Optional[List[Dict[str, Any]]]) -> Optional[Path]:
        """
        保存聊天历史到文件
        
        Args:
            commit_id: 提交ID
            chat_history: 聊天历史记录
            
        Returns:
            聊天历史文件路径，如果没有历史记录则返回None
        """
        if not chat_history:
            return None
            
        chat_history_path = self.config.chat_histories_dir / f"{commit_id}_chat.json"
        chat_history_path.write_text(
            json.dumps(chat_history[-2:], indent=2, ensure_ascii=False, default=str),
            encoding='utf-8'
        )
        logger.info(f"保存聊天历史: {chat_history_path}")
        return chat_history_path

    def _create_node_metadata(
        self, 
        commit_id: str, 
        parent_commit_id: Optional[str], 
        message: str, 
        step: int, 
        chat_history_path: Optional[Path],
        is_stopped: str = "continue"
    ) -> GitTreeNode:
        """
        创建Git树节点并保存元数据
        
        Args:
            commit_id: 提交ID
            parent_commit_id: 父提交ID
            message: 提交消息
            step: 步骤索引
            chat_history_path: 聊天历史文件路径
            is_stopped: 是否停止状态，默认为"continue"
            
        Returns:
            创建的GitTreeNode节点
        """
        # 创建节点
        node = GitTreeNode(
            commit_id=commit_id,
            parent_commit_id=parent_commit_id,
            message=message,
            step_index=step,
            chat_history_path=chat_history_path,
            is_stopped=is_stopped
        )

        # 保存元数据
        metadata_path = self.config.git_step_infor_dir / f"{commit_id}_metadata.json"
        metadata = {
            "commit_id": commit_id,
            "parent_commit_id": parent_commit_id,
            "message": message,
            "step_index": step,
            "branch_name": commit_id,  # 分支名就是提交ID
            "chat_history_path": str(chat_history_path) if chat_history_path else None
        }

        metadata_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False, default=str),
            encoding='utf-8'
        )

        node.metadata_path = metadata_path
        return node

    def commit_to_existing_branch(
        self,
        message: str,
        commit_id: str,
        parent_commit_id: Optional[str] = None,
        step: int = 0,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        is_stopped: str = "continue"
    ):
        """
        在现有分支上创建提交（不创建新分支）
        
        适用于需要先切换到现有分支，执行操作后再提交的场景
        
        Args:
            message: 提交消息
            parent_commit_id: 父提交ID（现有分支名）
            step: beam步骤索引
            chat_history: 聊天历史记录
            is_stopped: 是否停止状态，默认为"continue"
            
        Returns:
            提交ID
        """
        # 1. 确保在正确的分支上（不创建新分支）
        self._run_git_command(["checkout", commit_id])
        logger.info(f"检出到现有分支: {commit_id}")

        # 2. 提交更改
        has_changes = self._commit_changes(message)
        if not has_changes:
            logger.info("工作区没有更改，跳过提交，返回现有分支名")

        # 3. 保存聊天历史
        chat_history_path = self._save_chat_history(commit_id, chat_history)

        # 4. 更新已存在的节点信息
        if commit_id in self.storage_manager.nodes:
            # 更新现有节点的信息
            node = self.storage_manager.nodes[commit_id]
            node.message = message
            node.chat_history_path = chat_history_path
            node.metadata_path = self.config.git_step_infor_dir / f"{commit_id}_metadata.json"
            
            # 保存更新后的元数据
            metadata = {
                "commit_id": commit_id,
                "parent_commit_id": parent_commit_id,
                "message": message,
                "step_index": step,
                "branch_name": commit_id,
                "chat_history_path": str(chat_history_path) if chat_history_path else None
            }
            
            node.metadata_path.write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False, default=str),
                encoding='utf-8'
            )
        else:
            # 如果节点不存在，创建新节点（这种情况不应该发生）
            logger.warning(f"节点 {commit_id} 不存在，创建新节点")
            node = self._create_node_metadata(commit_id, parent_commit_id, message, step, chat_history_path)
            self.storage_manager.add_node(node)

        # 5. 保存树结构
        self.storage_manager.save_tree()

        logger.info(f"在现有分支上创建提交: {commit_id} - {message}")

    def _create_branch_and_commit(
            self,
            parent_commit_id: Optional[str] = None,
            step: int = 0,
            index: int = 0
    ) -> str:
        # 生成提交ID（作为分支名）
        commit_id = f"beam_step_{step}_index_{index}_{IDGenerator.generate_commit_id()[:8]}"

        # 1. 创建分支
        self._create_branch(commit_id, parent_commit_id)
        
        # 2. 创建节点（此时还没有聊天历史和元数据，后续会更新）
        node = GitTreeNode(
            commit_id=commit_id,
            parent_commit_id=parent_commit_id,
            message=f"Step {step} index {index}",
            step_index=step
        )
        
        # 3. 添加到存储以建立父子关系
        self.storage_manager.add_node(node)
        self.storage_manager.save_tree()
        
        return commit_id

    def create_commit(
            self,
            message: str,
            parent_commit_id: Optional[str] = None,
            step: int = 0,
            chat_history: Optional[List[Dict[str, Any]]] = None,
            is_stopped: str = "continue"
    ) -> str:
        """
        创建一个新的提交（包含新分支创建）
        
        Args:
            message: 提交消息
            parent_commit_id: 父提交ID（即分支名）
            step: beam步骤索引
            chat_history: 聊天历史记录
            is_stopped: 是否停止状态，默认为"continue"
            
        Returns:
            新创建的提交ID（即分支名）
        """
        # 生成提交ID（作为分支名）
        commit_id = f"beam_step_{step}_{IDGenerator.generate_commit_id()[:8]}"

        # 1. 创建分支
        self._create_branch(commit_id, parent_commit_id)

        # 2. 提交更改
        self._commit_changes(message)

        # 3. 保存聊天历史
        chat_history_path = self._save_chat_history(commit_id, chat_history)

        # 4. 创建节点和元数据
        node = self._create_node_metadata(commit_id, parent_commit_id, message, step, chat_history_path, is_stopped)

        # 5. 添加到存储
        self.storage_manager.add_node(node)
        self.storage_manager.save_tree()

        logger.info(f"创建提交: {commit_id} - {message}")
        return commit_id

    def checkout_to_commit(self,  commit_id: str) -> bool:
        """检出到指定提交状态"""
        try:
            #cd 到工作区
            # 直接检出到对应分支
            self._run_git_command(["checkout", commit_id])
            logger.info(f"检出到提交: {commit_id}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"检出失败: {commit_id}, 错误: {e}")
            return False


    def get_commit_info(self, commit_id: str) -> Optional[Dict[str, Any]]:
        """获取提交信息"""
        node = self.storage_manager.get_node(commit_id)
        if not node:
            return None

        return {
            "commit_id": node.commit_id,
            "message": node.message,
            "parent_commit_id": node.parent_commit_id,
            "children": node.children,
            "beam_path_id": node.beam_path_id,
            "step_index": node.step_index,
            "branch_name": commit_id,
            "chat_history_path": str(node.chat_history_path) if node.chat_history_path else None,
            "score": node.score,
            "judge_path": node.judge_path
        }

    def get_commit_path(self, commit_id: str) -> List[Dict[str, Any]]:
        """获取从根到指定提交的路径"""
        path = self.storage_manager.get_commit_path(commit_id)
        return [node.to_dict() for node in path]

    def get_tree_structure(self) -> Dict[str, Any]:
        """获取树结构"""
        return self.storage_manager.export_tree_structure()

    def print_tree(self) -> None:
        """打印树结构"""
        # 获取所有分支
        try:
            branches = self._run_git_command(["branch", "-a"]).split('\n')
            beam_branches = [b.strip().replace('* ', '') for b in branches if 'beam_step_' in b]
            
            print("\nGit提交树:")
            for branch in sorted(beam_branches):
                # 获取分支信息
                try:
                    info = self._run_git_command(["log", "-1", "--pretty=format:%s", branch])
                    print(f"├── {branch} - {info}")
                except:
                    print(f"├── {branch}")
        except Exception as e:
            logger.error(f"打印树结构失败: {e}")
            # 回退到存储的树结构
            def print_tree_recursive(commit_id: str, prefix: str = "", visited: set = None):
                if visited is None:
                    visited = set()

                if commit_id not in self.storage_manager.nodes or commit_id in visited:
                    return

                visited.add(commit_id)
                node = self.storage_manager.nodes[commit_id]
                print(f"{prefix}├── {commit_id} - Step {node.step_index} - {node.message}")

                for child_id in node.children:
                    print_tree_recursive(child_id, prefix + "│   ", visited)

            print("\nGit提交树 (存储结构):")
            for root_id in self.storage_manager.metadata.root_commits:
                print_tree_recursive(root_id)

    def cleanup_old_branches(self, keep_commits: List[str]) -> None:
        """清理旧的分支"""
        try:
            # 获取所有beam分支
            branches = self._run_git_command(["branch", "--list", "beam_step_*"]).split('\n')
            all_branches = [b.strip() for b in branches if b.strip()]
            
            # 删除不需要的分支
            for branch in all_branches:
                if branch not in keep_commits:
                    try:
                        self._run_git_command(["branch", "-D", branch])
                        logger.info(f"删除旧分支: {branch}")
                    except:
                        pass  # 忽略删除失败的分支
        except Exception as e:
            logger.error(f"清理旧分支失败: {e}")

    def cleanup_all_beam_branches(self) -> None:
        """清理所有 beam_step_* 分支（本地+远程）"""
        try:
            #先切到主分支
            self._run_git_command(["checkout", self.main_branch])
            # 1. 本地分支 ----------------------------------------------------------
            locals = self._run_git_command(
                ["branch", "--format=%(refname:short)", "--list", "beam_step_*"]
            ).splitlines()
            locals = [b for b in locals if b]  # 去掉空串

            if locals:
                # 一条命令批量删本地
                self._run_git_command(["branch", "-D", *locals])
                logger.info("已删除本地 beam_step_* 分支: %s", locals)

            if not locals:
                logger.info("未发现 beam_step_* 分支，无需清理")

        except subprocess.CalledProcessError as e:
            logger.error("清理 beam_step 分支失败: %s", e.stderr or e)

    def cleanup_git_locks(self) -> Dict[str, Any]:
        """
        手动清理Git锁文件
        
        Returns:
            清理结果统计
        """
        git_dir = Path(self.base_workspace) / '.git'
        lock_files = [
            git_dir / 'index.lock',
            git_dir / 'refs' / 'heads.lock',
            git_dir / 'packed-refs.lock',
            git_dir / 'config.lock',
            git_dir / 'shallow.lock',
            git_dir / 'HEAD.lock'
        ]
        
        result = {
            "cleaned_files": [],
            "failed_files": [],
            "total_files": len(lock_files)
        }
        
        for lock_file in lock_files:
            if lock_file.exists():
                try:
                    lock_file.unlink()
                    result["cleaned_files"].append(str(lock_file))
                    logger.info(f"成功清理锁文件: {lock_file}")
                except (OSError, PermissionError) as e:
                    result["failed_files"].append({
                        "file": str(lock_file),
                        "error": str(e)
                    })
                    logger.warning(f"清理锁文件失败: {lock_file}, 错误: {e}")
        
        return result

    def merge_branch_to_main(self,
                             source_branch: str,
                             target_branch: Optional[str] = None) -> bool:
        """
        把 source_branch 相对 target_branch 的所有"非空"提交
        逐个搬到 target_branch 工作区（不提交）。
        """
        if target_branch is None:
            target_branch = self.main_branch
            
        try:
            for br in (source_branch, target_branch):
                self._run_git_command(["rev-parse", "--verify", br])
        except subprocess.CalledProcessError:
            logger.warning(f"分支 {source_branch} 或 {target_branch} 不存在，跳过合并")
            return False

        logger.info(f"开始将 {source_branch} 的提交搬到 {target_branch} 工作区（不提交）")

        current_branch = self._run_git_command(["rev-parse", "--abbrev-ref", "HEAD"]).strip()

        try:
            # 1. 站到目标分支
            self._run_git_command(["checkout", target_branch])

            # 2. 拿到 source_branch 相对 target_branch 的提交（按时间顺序）
            commits = self._run_git_command(
                ["rev-list", "--reverse", f"{target_branch}..{source_branch}"]
            ).splitlines()

            if not commits or commits == ['']:
                logger.info("没有需要搬运的提交")
                return True

            # 4. 逐个 cherry-pick，不自动提交
            for commit in commits:
                self._run_git_command(["cherry-pick", "--no-commit", commit])
                logger.debug(f"已应用提交 {commit[:8]} 到工作区")

            logger.info(f"成功将 {len(commits)} 个非空提交搬到 {target_branch} 工作区（未提交）")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"搬运提交失败: {e}")
            # 中止并回退
            try:
                self._run_git_command(["cherry-pick", "--abort"])
            except Exception:
                pass
            self._run_git_command(["reset", "--hard", target_branch])
            return False