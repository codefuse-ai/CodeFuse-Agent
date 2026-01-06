"""Configuration management module"""
from pathlib import Path
from dataclasses import dataclass
import os


@dataclass
class GitTreeConfig:
    """GitTree configuration class"""
    diff_workspace: Path
    base_workspace: Path
    max_workspaces: int = 2

    @property
    def run_dir(self) -> Path:
        """Run space directory"""
        return self.diff_workspace / "run"

    @property
    def beam_path_infor(self) -> Path:
        """beam_path_infor directory"""
        return self.diff_workspace / "beam_path_infor"

    @property
    def judge_path(self) -> Path:
        """beam_path_infor directory"""
        return self.diff_workspace / "judge"

    @property
    def git_tree_dir(self) -> Path:
        """git_tree directory"""
        return self.diff_workspace / "git_tree"

    @property
    def git_step_infor_dir(self) -> Path:
        """git step information storage directory"""
        return self.git_tree_dir / "git_step_infor"

    @property
    def chat_histories_dir(self) -> Path:
        """Chat history storage directory"""
        return self.git_tree_dir / "chat_histories"

    @property
    def tree_file(self) -> Path:
        """Tree structure file"""
        return self.git_tree_dir / "tree.json"

    def ensure_directories(self) -> None:
        """Ensure all necessary directories exist, clean existing files first"""
        import shutil

        # Clean existing directories and files
        directories_to_clean = [
            self.run_dir,
            self.beam_path_infor,
            self.judge_path,
            self.git_tree_dir,
            self.git_step_infor_dir,
            self.chat_histories_dir
        ]

        for directory in directories_to_clean:
            if directory.exists():
                shutil.rmtree(directory)

        # Delete tree.json file if it exists
        if self.tree_file.exists():
            self.tree_file.unlink()

        # Recreate all directories
        directories = [
            self.run_dir,
            self.beam_path_infor,
            self.judge_path,
            self.git_tree_dir,
            self.git_step_infor_dir,
            self.chat_histories_dir
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


def load_config_from_env() -> GitTreeConfig:
    """Load configuration from environment variables"""
    diff_workspace = Path(os.getenv(
        "diff_workspace",
        "/Users/jiawan/projects/SWE-bench_Verified/beam/chat_history/lzy-test__linkc-fork_2/output"
    ))
    base_workspace = Path(os.getenv(
        "base_workspace",
        "/Users/jiawan/projects/ant/linkc-fork"
    ))
    max_workspaces = int(os.getenv("GIT_TREE_MAX_WORKSPACES", "2"))

    return GitTreeConfig(
        diff_workspace=diff_workspace,
        base_workspace=base_workspace,
        max_workspaces=max_workspaces
    )


def load_config_from_user(base_workspace: Path, diff_workspace: Path, max_workspaces: int) -> GitTreeConfig:
    """Load configuration from user input"""
    return GitTreeConfig(
        diff_workspace=diff_workspace,
        base_workspace=base_workspace,
        max_workspaces=max_workspaces
    )