"""树存储管理器"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

from ..models.node import GitTreeNode, TreeMetadata
from ..config.settings import GitTreeConfig

logger = logging.getLogger(__name__)


class TreeStorageManager:
    """树存储管理器，负责树的持久化存储"""
    
    def __init__(self, config: GitTreeConfig):
        """初始化存储管理器"""
        self.config = config
        self.config.ensure_directories()
        
        self.nodes: Dict[str, GitTreeNode] = {}
        self.metadata = TreeMetadata()

        self._load_existing_tree()
    
    def _load_existing_tree(self) -> None:
        """加载已存在的git树"""
        if not self.config.tree_file.exists():
            logger.info("未找到现有树文件，创建新树")
            return

        try:
            with open(self.config.tree_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.metadata = TreeMetadata.from_dict(data)

            # 加载节点
            for node_data in data.get("nodes", []):
                node = GitTreeNode.from_dict(node_data)
                self.nodes[node.commit_id] = node

            logger.info(f"已加载现有git树，包含 {len(self.nodes)} 个节点")

        except Exception as e:
            logger.error(f"加载git树失败: {e}")
            # 如果加载失败，创建新的空树
            self.nodes = {}
            self.metadata = TreeMetadata()
    
    def save_tree(self) -> None:
        """保存git树到文件"""
        try:
            data = {
                **self.metadata.to_dict(),
                "nodes": [node.to_dict() for node in self.nodes.values()]
            }

            with open(self.config.tree_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"已保存git树，包含 {len(self.nodes)} 个节点")

        except Exception as e:
            logger.error(f"保存git树失败: {e}")
            raise

    def add_node(self, node: GitTreeNode) -> None:
        """添加节点"""
        self.nodes[node.commit_id] = node

        # 更新父节点的子节点列表
        if node.parent_commit_id and node.parent_commit_id in self.nodes:
            parent = self.nodes[node.parent_commit_id]
            parent.add_child(node.commit_id)
        else:
            # 根节点
            if node.commit_id not in self.metadata.root_commits:
                self.metadata.root_commits.append(node.commit_id)

    def get_node(self, commit_id: str) -> Optional[GitTreeNode]:
        """获取节点"""
        return self.nodes.get(commit_id)

    def get_commit_path(self, commit_id: str) -> List[GitTreeNode]:
        """获取从根到指定提交的路径"""
        if commit_id not in self.nodes:
            return []

        path = []
        current = self.nodes[commit_id]

        # 构建从当前节点到根节点的路径
        while current:
            path.insert(0, current)
            if not current.parent_commit_id:
                break
            if current.parent_commit_id not in self.nodes:
                break
            current = self.nodes[current.parent_id]

        return path

    def get_all_nodes(self) -> Dict[str, GitTreeNode]:
        """获取所有节点"""
        return self.nodes.copy()

    def get_root_nodes(self) -> List[GitTreeNode]:
        """获取所有根节点"""
        return [self.nodes[commit_id] for commit_id in self.metadata.root_commits
                if commit_id in self.nodes]

    def remove_node(self, commit_id: str) -> bool:
        """删除节点及其所有子节点"""
        if commit_id not in self.nodes:
            return False

        # 递归删除子节点
        node = self.nodes[commit_id]
        for child_id in node.children:
            self.remove_node(child_id)

        # 从父节点的子节点列表中移除
        if node.parent_commit_id and node.parent_commit_id in self.nodes:
            parent = self.nodes[node.parent_commit_id]
            if commit_id in parent.children:
                parent.children.remove(commit_id)

        # 从根节点列表中移除
        if commit_id in self.metadata.root_commits:
            self.metadata.root_commits.remove(commit_id)

        # 删除节点
        del self.nodes[commit_id]
        logger.info(f"删除节点: {commit_id}")

        return True

    def clear_tree(self) -> None:
        """清空整个树"""
        self.nodes.clear()
        self.metadata = TreeMetadata()
        logger.info("已清空git树")

    def export_tree_structure(self) -> Dict[str, Any]:
        """导出树结构用于调试"""
        return {
            "metadata": self.metadata.to_dict(),
            "nodes": {commit_id: node.to_dict() for commit_id, node in self.nodes.items()},
            "total_nodes": len(self.nodes),
            "root_nodes": len(self.metadata.root_commits)
        }