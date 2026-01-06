"""Tree storage manager"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

from ..models.node import GitTreeNode, TreeMetadata
from ..config.settings import GitTreeConfig

logger = logging.getLogger(__name__)


class TreeStorageManager:
    """Tree storage manager, responsible for tree persistence"""
    
    def __init__(self, config: GitTreeConfig):
        """Initialize storage manager"""
        self.config = config
        self.config.ensure_directories()
        
        self.nodes: Dict[str, GitTreeNode] = {}
        self.metadata = TreeMetadata()

        self._load_existing_tree()
    
    def _load_existing_tree(self) -> None:
        """Load existing git tree"""
        if not self.config.tree_file.exists():
            logger.info("No existing tree file found, creating new tree")
            return

        try:
            with open(self.config.tree_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.metadata = TreeMetadata.from_dict(data)

            # Load nodes
            for node_data in data.get("nodes", []):
                node = GitTreeNode.from_dict(node_data)
                self.nodes[node.commit_id] = node

            logger.info(f"Loaded existing git tree with {len(self.nodes)} nodes")

        except Exception as e:
            logger.error(f"Failed to load git tree: {e}")
            # Create new empty tree if loading fails
            self.nodes = {}
            self.metadata = TreeMetadata()
    
    def save_tree(self) -> None:
        """Save git tree to file"""
        try:
            data = {
                **self.metadata.to_dict(),
                "nodes": [node.to_dict() for node in self.nodes.values()]
            }

            with open(self.config.tree_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"Saved git tree with {len(self.nodes)} nodes")

        except Exception as e:
            logger.error(f"Failed to save git tree: {e}")
            raise

    def add_node(self, node: GitTreeNode) -> None:
        """Add node"""
        self.nodes[node.commit_id] = node

        # Update parent node's child list
        if node.parent_commit_id and node.parent_commit_id in self.nodes:
            parent = self.nodes[node.parent_commit_id]
            parent.add_child(node.commit_id)
        else:
            # Root node
            if node.commit_id not in self.metadata.root_commits:
                self.metadata.root_commits.append(node.commit_id)

    def get_node(self, commit_id: str) -> Optional[GitTreeNode]:
        """Get node"""
        return self.nodes.get(commit_id)

    def get_commit_path(self, commit_id: str) -> List[GitTreeNode]:
        """Get path from root to specified commit"""
        if commit_id not in self.nodes:
            return []

        path = []
        current = self.nodes[commit_id]

        # Build path from current node to root node
        while current:
            path.insert(0, current)
            if not current.parent_commit_id:
                break
            if current.parent_commit_id not in self.nodes:
                break
            current = self.nodes[current.parent_commit_id]

        return path

    def get_all_nodes(self) -> Dict[str, GitTreeNode]:
        """Get all nodes"""
        return self.nodes.copy()

    def get_root_nodes(self) -> List[GitTreeNode]:
        """Get all root nodes"""
        return [self.nodes[commit_id] for commit_id in self.metadata.root_commits
                if commit_id in self.nodes]

    def remove_node(self, commit_id: str) -> bool:
        """Delete node and all its child nodes"""
        if commit_id not in self.nodes:
            return False

        # Recursively delete child nodes
        node = self.nodes[commit_id]
        for child_id in node.children:
            self.remove_node(child_id)

        # Remove from parent node's child list
        if node.parent_commit_id and node.parent_commit_id in self.nodes:
            parent = self.nodes[node.parent_commit_id]
            if commit_id in parent.children:
                parent.children.remove(commit_id)

        # Remove from root node list
        if commit_id in self.metadata.root_commits:
            self.metadata.root_commits.remove(commit_id)

        # Delete node
        del self.nodes[commit_id]
        logger.info(f"Deleted node: {commit_id}")

        return True

    def clear_tree(self) -> None:
        """Clear entire tree"""
        self.nodes.clear()
        self.metadata = TreeMetadata()
        logger.info("Cleared git tree")

    def export_tree_structure(self) -> Dict[str, Any]:
        """Export tree structure for debugging"""
        return {
            "metadata": self.metadata.to_dict(),
            "nodes": {commit_id: node.to_dict() for commit_id, node in self.nodes.items()},
            "total_nodes": len(self.nodes),
            "root_nodes": len(self.metadata.root_commits)
        }