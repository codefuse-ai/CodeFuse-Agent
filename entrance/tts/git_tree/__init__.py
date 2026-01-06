"""GitTree - Enhanced Git tree management tool"""

__version__ = "2.0.0"
__author__ = "GitTree Team"

from .managers.git_tree_manager_simplified import GitTreeManagerSimplified as GitTreeManager
from .config.settings import GitTreeConfig, load_config_from_env
from .models.node import GitTreeNode

__all__ = [
    "GitTreeManager",
    "GitTreeConfig", 
    "load_config_from_env",
    "GitTreeNode"
]