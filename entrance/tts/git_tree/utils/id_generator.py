"""ID generation utilities"""
import hashlib
import secrets
from datetime import datetime
from typing import Optional


class IDGenerator:
    """ID generator"""
    
    @staticmethod
    def generate_commit_id(timestamp: Optional[datetime] = None) -> str:
        """Generate commit ID"""
        if timestamp is None:
            timestamp = datetime.now()
        
        timestamp_str = str(int(timestamp.timestamp()))
        random_hash = secrets.token_hex(4)  # 8-character random string
        return f"{timestamp_str}_{random_hash}"
    
    @staticmethod
    def generate_beam_path_id() -> str:
        """Generate beam path ID"""
        return secrets.token_hex(8)
    
    @staticmethod
    def generate_workspace_id(index: int) -> str:
        """Generate workspace ID"""
        return f"workspace_{index}"
    
    @staticmethod
    def hash_content(content: str) -> str:
        """Generate content hash"""
        return hashlib.sha256(content.encode()).hexdigest()[:16]