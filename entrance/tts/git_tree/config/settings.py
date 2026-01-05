"""配置管理模块"""
from pathlib import Path
from dataclasses import dataclass
import os


@dataclass
class GitTreeConfig:
    """GitTree配置类"""
    diff_workspace: Path
    base_workspace: Path
    max_workspaces: int = 2

    @property
    def run_dir(self) -> Path:
        """运行空间目录"""
        return self.diff_workspace / "run"

    @property
    def beam_path_infor(self) -> Path:
        """beam_path_infor目录"""
        return self.diff_workspace / "beam_path_infor"

    @property
    def judge_path(self) -> Path:
        """beam_path_infor目录"""
        return self.diff_workspace / "judge"

    @property
    def git_tree_dir(self) -> Path:
        """git_tree目录"""
        return self.diff_workspace / "git_tree"



    @property
    def git_step_infor_dir(self) -> Path:
        """git step信息存储目录"""
        return self.git_tree_dir / "git_step_infor"

    @property
    def chat_histories_dir(self) -> Path:
        """聊天历史存储目录"""
        return self.git_tree_dir / "chat_histories"

    @property
    def tree_file(self) -> Path:
        """树结构文件"""
        return self.git_tree_dir / "tree.json"

    def ensure_directories(self) -> None:
        """确保所有必要的目录存在，先清理已存在的文件"""
        import shutil

        # 清理已存在的目录和文件
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

        # 如果tree.json文件存在，也删除
        if self.tree_file.exists():
            self.tree_file.unlink()

        # 重新创建所有目录
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
    """从环境变量加载配置"""
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
    """从用户输入加载配置"""
    return GitTreeConfig(
        diff_workspace=diff_workspace,
        base_workspace=base_workspace,
        max_workspaces=max_workspaces
    )