"""工作空间管理器"""
import shutil
import threading
from pathlib import Path
import logging
from ..utils.file_utils import FileManager

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """工作空间管理器，维护运行空间"""
    
    def __init__(self, run_dir: Path, base_workspace: Path, max_workspaces: int = 2):
        """
        初始化工作空间管理器
        
        Args:
            base_workspace：基准工作空间路径
            max_workspaces: 最大工作空间数量
        """
        self.run_dir = run_dir
        self.base_workspace = base_workspace
        self.max_workspaces = max_workspaces

        self.lock = threading.Lock()

        self._init_workspaces()

    def _init_workspaces(self) -> None:
        """初始化工作空间 - 简化的设计"""
        with self.lock:
            for i in range(self.max_workspaces):
                workspace_id = f"workspace_{i}"
                workspace_path = self.run_dir / workspace_id
                if workspace_path.exists():
                    logger.info(f"存储目录 {workspace_path} 已存在，清空")
                    shutil.rmtree(workspace_path)
                workspace_path.mkdir(parents=True, exist_ok=True)

    def copy_base_to_workspace(self, workspace_path: Path) -> None:
        """
        将基准工作空间复制到指定工作空间
        
        Args:
            workspace_path: 目标工作空间路径
        """
        FileManager().safe_copy_tree(Path(self.base_workspace), workspace_path)

    #随机返回一个空的工作空间
    def get_empty_workspace(self) -> Path:
        """
        获取一个空的工作空间
        """
        with self.lock:
            workspace_path = self.run_dir
            if workspace_path.exists():
                logger.info(f"存储目录 {workspace_path} 已存在，清空")
                shutil.rmtree(workspace_path)
            workspace_path.mkdir(parents=True, exist_ok=True)
            return workspace_path

    
    