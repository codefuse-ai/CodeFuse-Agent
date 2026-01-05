"""简化版的Diff处理工具类 - 使用Git命令"""
import subprocess
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class SimplifiedDiffProcessor:
    """简化版的Diff处理类，使用Git命令"""
    
    def __init__(self, repo_path: Path):
        """初始化，指定Git仓库路径"""
        self.repo_path = repo_path
    
    def _run_git_command(self, cmd: List[str]) -> str:
        """运行Git命令"""
        try:
            result = subprocess.run(
                ["git"] + cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Git命令失败: {' '.join(cmd)}, 错误: {e.stderr}")
            raise
    
    def create_diff(self, from_ref: str, to_ref: str) -> str:
        """
        创建两个引用之间的diff
        
        Args:
            from_ref: 源引用（分支名、提交哈希等）
            to_ref: 目标引用
            
        Returns:
            diff内容
        """
        return self._run_git_command(["diff", from_ref, to_ref])
    
    def apply_diff_from_file(self, diff_file: Path) -> None:
        """
        从diff文件应用更改
        
        Args:
            diff_file: diff文件路径
        """
        if not diff_file.exists():
            logger.warning(f"diff文件不存在: {diff_file}")
            return
            
        try:
            # 使用git apply应用diff
            subprocess.run(
                ["git", "apply", str(diff_file)],
                cwd=self.repo_path,
                check=True
            )
            logger.info(f"应用diff文件: {diff_file}")
        except subprocess.CalledProcessError as e:
            # 如果git apply失败，尝试使用patch
            logger.warning(f"git apply失败，尝试使用patch: {e}")
            try:
                subprocess.run(
                    ["patch", "-p1", "<", str(diff_file)],
                    cwd=self.repo_path,
                    shell=True,
                    check=True
                )
            except subprocess.CalledProcessError as e2:
                logger.error(f"应用diff失败: {e2}")
                raise
    
    def get_file_content_at_ref(self, file_path: str, ref: str) -> Optional[str]:
        """
        获取指定引用下的文件内容
        
        Args:
            file_path: 文件路径
            ref: 引用（分支名、提交哈希等）
            
        Returns:
            文件内容，如果文件不存在则返回None
        """
        try:
            content = self._run_git_command(["show", f"{ref}:{file_path}"])
            return content
        except subprocess.CalledProcessError:
            return None
    
    def list_changed_files(self, from_ref: str, to_ref: str) -> List[str]:
        """
        获取两个引用之间更改的文件列表
        
        Args:
            from_ref: 源引用
            to_ref: 目标引用
            
        Returns:
            更改的文件列表
        """
        output = self._run_git_command(["diff", "--name-only", from_ref, to_ref])
        return [line.strip() for line in output.split('\n') if line.strip()]
    
    def has_changes(self, ref: str = "HEAD") -> bool:
        """
        检查工作区是否有未提交的更改
        
        Args:
            ref: 引用，默认为HEAD
            
        Returns:
            是否有更改
        """
        try:
            output = self._run_git_command(["diff", "--quiet", ref])
            return False  # 没有更改
        except subprocess.CalledProcessError:
            return True  # 有更改
    
    def get_current_branch(self) -> str:
        """获取当前分支名"""
        return self._run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
    
    def branch_exists(self, branch_name: str) -> bool:
        """检查分支是否存在"""
        try:
            self._run_git_command(["rev-parse", "--verify", branch_name])
            return True
        except subprocess.CalledProcessError:
            return False
    
    def create_branch(self, branch_name: str, from_ref: str = "HEAD") -> None:
        """创建新分支"""
        self._run_git_command(["checkout", "-b", branch_name, from_ref])
        logger.info(f"创建分支: {branch_name} 从 {from_ref}")
    
    def switch_branch(self, branch_name: str) -> None:
        """切换到指定分支"""
        self._run_git_command(["checkout", branch_name])
        logger.info(f"切换到分支: {branch_name}")
    
    def delete_branch(self, branch_name: str, force: bool = False) -> None:
        """删除分支"""
        cmd = ["branch", "-D" if force else "-d", branch_name]
        self._run_git_command(cmd)
        logger.info(f"删除分支: {branch_name}")
    
    def get_commit_hash(self, ref: str) -> str:
        """获取引用的提交哈希"""
        return self._run_git_command(["rev-parse", ref])
    
    def get_commit_info(self, ref: str) -> dict:
        """获取提交信息"""
        format_string = "%H|%an|%ae|%ad|%s"
        output = self._run_git_command(["log", "-1", f"--pretty=format:{format_string}", ref])
        parts = output.split("|")
        return {
            "hash": parts[0],
            "author": parts[1],
            "email": parts[2],
            "date": parts[3],
            "message": parts[4]
        }