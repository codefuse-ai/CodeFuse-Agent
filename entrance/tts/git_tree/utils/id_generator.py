"""ID生成工具"""
import hashlib
import secrets
from datetime import datetime
from typing import Optional


class IDGenerator:
    """ID生成器"""
    
    @staticmethod
    def generate_commit_id(timestamp: Optional[datetime] = None) -> str:
        """生成提交ID"""
        if timestamp is None:
            timestamp = datetime.now()
        
        timestamp_str = str(int(timestamp.timestamp()))
        random_hash = secrets.token_hex(4)  # 8位随机字符串
        return f"{timestamp_str}_{random_hash}"
    
    @staticmethod
    def generate_beam_path_id() -> str:
        """生成beam路径ID"""
        return secrets.token_hex(8)
    
    @staticmethod
    def generate_workspace_id(index: int) -> str:
        """生成工作空间ID"""
        return f"workspace_{index}"
    
    @staticmethod
    def hash_content(content: str) -> str:
        """生成内容哈希"""
        return hashlib.sha256(content.encode()).hexdigest()[:16]