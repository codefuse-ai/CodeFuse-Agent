"""Simplified Diff processing utility class - using Git commands"""
import subprocess
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class SimplifiedDiffProcessor:
    """Simplified Diff processing class using Git commands"""
    
    def __init__(self, repo_path: Path):
        """Initialize, specify Git repository path"""
        self.repo_path = repo_path
    
    def _run_git_command(self, cmd: List[str]) -> str:
        """Run Git command"""
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
            logger.error(f"Git command failed: {' '.join(cmd)}, error: {e.stderr}")
            raise
    
    def create_diff(self, from_ref: str, to_ref: str) -> str:
        """
        Create diff between two references
        
        Args:
            from_ref: Source reference (branch name, commit hash, etc.)
            to_ref: Target reference
            
        Returns:
            diff content
        """
        return self._run_git_command(["diff", from_ref, to_ref])
    
    def apply_diff_from_file(self, diff_file: Path) -> None:
        """
        Apply changes from diff file
        
        Args:
            diff_file: diff file path
        """
        if not diff_file.exists():
            logger.warning(f"diff file does not exist: {diff_file}")
            return
            
        try:
            # Use git apply to apply diff
            subprocess.run(
                ["git", "apply", str(diff_file)],
                cwd=self.repo_path,
                check=True
            )
            logger.info(f"Applied diff file: {diff_file}")
        except subprocess.CalledProcessError as e:
            # If git apply fails, try using patch
            logger.warning(f"git apply failed, trying patch: {e}")
            try:
                subprocess.run(
                    ["patch", "-p1", "<", str(diff_file)],
                    cwd=self.repo_path,
                    shell=True,
                    check=True
                )
            except subprocess.CalledProcessError as e2:
                logger.error(f"Failed to apply diff: {e2}")
                raise
    
    def get_file_content_at_ref(self, file_path: str, ref: str) -> Optional[str]:
        """
        Get file content at specified reference
        
        Args:
            file_path: file path
            ref: reference (branch name, commit hash, etc.)
            
        Returns:
            file content, returns None if file doesn't exist
        """
        try:
            content = self._run_git_command(["show", f"{ref}:{file_path}"])
            return content
        except subprocess.CalledProcessError:
            return None
    
    def list_changed_files(self, from_ref: str, to_ref: str) -> List[str]:
        """
        Get list of changed files between two references
        
        Args:
            from_ref: source reference
            to_ref: target reference
            
        Returns:
            list of changed files
        """
        output = self._run_git_command(["diff", "--name-only", from_ref, to_ref])
        return [line.strip() for line in output.split('\n') if line.strip()]
    
    def has_changes(self, ref: str = "HEAD") -> bool:
        """
        Check if workspace has uncommitted changes
        
        Args:
            ref: reference, defaults to HEAD
            
        Returns:
            whether there are changes
        """
        try:
            output = self._run_git_command(["diff", "--quiet", ref])
            return False  # no changes
        except subprocess.CalledProcessError:
            return True  # has changes
    
    def get_current_branch(self) -> str:
        """Get current branch name"""
        return self._run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
    
    def branch_exists(self, branch_name: str) -> bool:
        """Check if branch exists"""
        try:
            self._run_git_command(["rev-parse", "--verify", branch_name])
            return True
        except subprocess.CalledProcessError:
            return False
    
    def create_branch(self, branch_name: str, from_ref: str = "HEAD") -> None:
        """Create new branch"""
        self._run_git_command(["checkout", "-b", branch_name, from_ref])
        logger.info(f"Created branch: {branch_name} from {from_ref}")
    
    def switch_branch(self, branch_name: str) -> None:
        """Switch to specified branch"""
        self._run_git_command(["checkout", branch_name])
        logger.info(f"Switched to branch: {branch_name}")
    
    def delete_branch(self, branch_name: str, force: bool = False) -> None:
        """Delete branch"""
        cmd = ["branch", "-D" if force else "-d", branch_name]
        self._run_git_command(cmd)
        logger.info(f"Deleted branch: {branch_name}")
    
    def get_commit_hash(self, ref: str) -> str:
        """Get commit hash for reference"""
        return self._run_git_command(["rev-parse", ref])
    
    def get_commit_info(self, ref: str) -> dict:
        """Get commit information"""
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