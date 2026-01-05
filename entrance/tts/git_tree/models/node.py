"""Git树节点模型"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class GitTreeNode:
    """表示git树中的一个节点"""
    commit_id: str
    parent_commit_id: Optional[str] = None
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    children: List[str] = field(default_factory=list)
    beam_path_id: Optional[str] = None
    step_index: int = 0
    chat_history_path: Optional[Path] = None
    metadata_path: Optional[Path] = None
    score: float = 0.0
    judge_path: Optional[Path] = None
    is_stopped: str = "continue"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式用于序列化"""
        return {
            "commit_id": self.commit_id,
            "parent_commit_id": self.parent_commit_id,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "children": self.children,
            "beam_path_id": self.beam_path_id,
            "step_index": self.step_index,

            "chat_history_path": str(self.chat_history_path) if self.chat_history_path else None,
            "metadata_path": str(self.metadata_path) if self.metadata_path else None,
            "score": self.score,
            "judge_path": self.judge_path,
            "is_stopped": self.is_stopped
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GitTreeNode:
        """从字典创建节点"""
        return cls(
            commit_id=data["commit_id"],
            parent_commit_id=data.get("parent_commit_id"),
            message=data.get("message", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            children=data.get("children", []),
            beam_path_id=data.get("beam_path_id"),
            step_index=data.get("step_index", 0),

            chat_history_path=Path(data["chat_history_path"]) if data.get("chat_history_path") else None,
            metadata_path=Path(data["metadata_path"]) if data.get("metadata_path") else None,
            score=data.get("score", 0.0),
            judge_path=Path(data["judge_path"]) if data.get("judge_path") else None,
            is_stopped=data.get("is_stopped", "continue")
        )

    def add_child(self, child_id: str) -> None:
        """添加子节点"""
        if child_id not in self.children:
            self.children.append(child_id)


@dataclass
class TreeMetadata:
    """树结构元数据"""
    base_commit: Optional[str] = None
    root_commits: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "base_commit": self.base_commit,
            "root_commits": self.root_commits
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TreeMetadata:
        """从字典创建"""
        return cls(
            base_commit=data.get("base_commit"),
            root_commits=data.get("root_commits", [])
        )