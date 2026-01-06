"""File operation utilities"""
import shutil
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class FileManager:
    """File management utilities"""

    @staticmethod
    def safe_copy_tree(src: Path, dst: Path) -> None:
        """Safely copy directory tree"""
        if not src.exists():
            raise FileNotFoundError(f"Source directory does not exist: {src}")

        if dst.exists():
            shutil.rmtree(dst)
            logger.info(f"Target directory already exists: {dst}")
        try:
            shutil.copytree(src, dst)
            logger.info(f"Successfully copied directory: {src} -> {dst}")
        except Exception as e:
            logger.error(f"Failed to copy directory: {src} -> {dst}, error: {e}")
            raise e

    @staticmethod
    def safe_remove(path: Path) -> None:
        """Safely delete file or directory"""
        if not path.exists():
            return

        try:
            if path.is_dir():
                shutil.rmtree(path)
                logger.info(f"Successfully deleted directory: {path}")
            else:
                path.unlink()
                logger.info(f"Successfully deleted file: {path}")
        except Exception as e:
            logger.error(f"Deletion failed: {path}, error: {e}")
            raise

    @staticmethod
    def ensure_directory(path: Path) -> None:
        """Ensure directory exists"""
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create directory: {path}, error: {e}")
            raise

    @staticmethod
    def is_safe_path(base_path: Path, target_path: Path) -> bool:
        """Check if path is within safe range"""
        try:
            target_path.resolve().relative_to(base_path.resolve())
            return True
        except ValueError:
            return False


class PathValidator:
    """Path validation utilities"""

    @staticmethod
    def validate_workspace_path(path: Path) -> None:
        """Validate workspace path"""
        if not path.exists():
            raise FileNotFoundError(f"Workspace does not exist: {path}")

        if not path.is_dir():
            raise NotADirectoryError(f"Workspace is not a directory: {path}")

    @staticmethod
    def validate_file_path(path: Path) -> None:
        """Validate file path"""
        if not path.exists():
            raise FileNotFoundError(f"File does not exist: {path}")

        if not path.is_file():
            raise IsADirectoryError(f"Path is a directory rather than a file: {path}")

    @staticmethod
    def validate_diff_path(path: Path, base_dir: Path) -> None:
        """Validate diff file path"""
        if not FileManager.is_safe_path(base_dir, path):
            raise ValueError(f"Invalid diff path: {path}")

        PathValidator.validate_file_path(path)