"""文件操作工具类"""
import shutil
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class FileManager:
    """文件管理工具类"""

    @staticmethod
    def safe_copy_tree(src: Path, dst: Path) -> None:
        """安全地复制目录树"""
        if not src.exists():
            raise FileNotFoundError(f"源目录不存在: {src}")

        if dst.exists():
            shutil.rmtree(dst)
            logger.info(f"目标目录已存在: {dst}")
        try:
            shutil.copytree(src, dst)
            logger.info(f"成功复制目录: {src} -> {dst}")
        except Exception as e:
            logger.error(f"复制目录失败: {src} -> {dst}, 错误: {e}")
            raise e

    @staticmethod
    def safe_remove(path: Path) -> None:
        """安全地删除文件或目录"""
        if not path.exists():
            return

        try:
            if path.is_dir():
                shutil.rmtree(path)
                logger.info(f"成功删除目录: {path}")
            else:
                path.unlink()
                logger.info(f"成功删除文件: {path}")
        except Exception as e:
            logger.error(f"删除失败: {path}, 错误: {e}")
            raise

    @staticmethod
    def ensure_directory(path: Path) -> None:
        """确保目录存在"""
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"创建目录失败: {path}, 错误: {e}")
            raise

    @staticmethod
    def is_safe_path(base_path: Path, target_path: Path) -> bool:
        """检查路径是否在安全范围内"""
        try:
            target_path.resolve().relative_to(base_path.resolve())
            return True
        except ValueError:
            return False


class PathValidator:
    """路径验证工具"""

    @staticmethod
    def validate_workspace_path(path: Path) -> None:
        """验证工作空间路径"""
        if not path.exists():
            raise FileNotFoundError(f"工作空间不存在: {path}")

        if not path.is_dir():
            raise NotADirectoryError(f"工作空间不是目录: {path}")

    @staticmethod
    def validate_file_path(path: Path) -> None:
        """验证文件路径"""
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")

        if not path.is_file():
            raise IsADirectoryError(f"路径是目录而非文件: {path}")

    @staticmethod
    def validate_diff_path(path: Path, base_dir: Path) -> None:
        """验证diff文件路径"""
        if not FileManager.is_safe_path(base_dir, path):
            raise ValueError(f"非法的diff路径: {path}")

        PathValidator.validate_file_path(path)