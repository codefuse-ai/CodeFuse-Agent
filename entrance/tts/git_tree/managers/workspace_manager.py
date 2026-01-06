"""Workspace manager"""
import shutil
import threading
from pathlib import Path
import logging
from ..utils.file_utils import FileManager

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """Workspace manager, maintains run space"""
    
    def __init__(self, run_dir: Path, base_workspace: Path, max_workspaces: int = 2):
        """
        Initialize workspace manager
        
        Args:
            base_workspace: Base workspace path
            max_workspaces: Maximum number of workspaces
        """
        self.run_dir = run_dir
        self.base_workspace = base_workspace
        self.max_workspaces = max_workspaces

        self.lock = threading.Lock()

        self._init_workspaces()

    def _init_workspaces(self) -> None:
        """Initialize workspaces - simplified design"""
        with self.lock:
            for i in range(self.max_workspaces):
                workspace_id = f"workspace_{i}"
                workspace_path = self.run_dir / workspace_id
                if workspace_path.exists():
                    logger.info(f"Storage directory {workspace_path} exists, clearing")
                    shutil.rmtree(workspace_path)
                workspace_path.mkdir(parents=True, exist_ok=True)

    def copy_base_to_workspace(self, workspace_path: Path) -> None:
        """
        Copy base workspace to specified workspace
        
        Args:
            workspace_path: Target workspace path
        """
        FileManager().safe_copy_tree(Path(self.base_workspace), workspace_path)

    # Randomly return an empty workspace
    def get_empty_workspace(self) -> Path:
        """
        Get an empty workspace
        """
        with self.lock:
            workspace_path = self.run_dir
            if workspace_path.exists():
                logger.info(f"Storage directory {workspace_path} exists, clearing")
                shutil.rmtree(workspace_path)
            workspace_path.mkdir(parents=True, exist_ok=True)
            return workspace_path