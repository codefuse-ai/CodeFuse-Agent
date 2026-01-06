"""Diff processing utility class"""
import difflib
import re
from pathlib import Path
from typing import List, Tuple
import logging

from .file_utils import FileManager

logger = logging.getLogger(__name__)


class DiffProcessor:
    """Diff processing class"""
    
    @staticmethod
    def _is_binary_file(file_path: Path) -> bool:
        """Check if file is binary"""
        if not file_path.exists():
            return False
            
        # Quick check based on file extension
        binary_extensions = {
            '.DS_Store', '.ico', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff',
            '.zip', '.tar', '.gz', '.rar', '.7z', '.exe', '.dll', '.so', '.dylib',
            '.bin', '.dat', '.db', '.sqlite', '.pyc', '.pyo', '.class', '.o', '.obj'
        }
        
        if file_path.suffix.lower() in binary_extensions:
            return True
            
        # Check based on file content
        try:
            with file_path.open('rb') as f:
                chunk = f.read(1024)
                if not chunk:
                    return False
                # Check for null bytes or large amounts of non-text characters
                if b'\x00' in chunk:
                    return True
                # Check text character ratio
                text_characters = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
                nontext = chunk.translate(None, text_characters)
                return float(len(nontext)) / len(chunk) > 0.30
        except (IOError, OSError):
            return True
            
    @staticmethod
    def create_diff(from_path: Path, to_path: Path) -> str:
        """Create unified diff between two paths"""
        if not from_path.exists():
            raise FileNotFoundError(f"Source path does not exist: {from_path}")
        if not to_path.exists():
            raise FileNotFoundError(f"Target path does not exist: {to_path}")
        
        diff_lines = []

        # Skip common binary files and git internal files
        skip_patterns = {
            '.DS_Store',
            '.git/',
            '__pycache__/',
            '.pyc',
            '.pyo',
            '.exe',
            '.dll',
            '.so',
            '.dylib'
        }
        
        if from_path.is_dir():
            from_files = {p.relative_to(from_path) for p in from_path.rglob('*') if p.is_file()}
        else:
            from_files = {Path(from_path.name)}
            
        if to_path.is_dir():
            to_files = {p.relative_to(to_path) for p in to_path.rglob('*') if p.is_file()}
        else:
            to_files = {Path(to_path.name)}
        
        all_files = from_files.union(to_files)
        
        for rel_path in sorted(all_files):
            # Skip matching files
            rel_path_str = str(rel_path)
            if any(pattern in rel_path_str for pattern in skip_patterns):
                continue
                
            from_file = from_path / rel_path if from_path.is_dir() else from_path
            to_file = to_path / rel_path if to_path.is_dir() else to_path
            
            # Check if binary file
            if (from_file.exists() and DiffProcessor._is_binary_file(from_file)) or \
               (to_file.exists() and DiffProcessor._is_binary_file(to_file)):
                continue
            
            from_content = ""
            to_content = ""
            
            try:
                if from_file.exists():
                    from_content = from_file.read_text(encoding='utf-8')
                if to_file.exists():
                    to_content = to_file.read_text(encoding='utf-8')
            except (UnicodeDecodeError, IOError) as e:
                logger.debug(f"Skipping file {rel_path}: {e}")
                continue
            
            if from_content != to_content:
                from_lines = from_content.splitlines(keepends=True)
                to_lines = to_content.splitlines(keepends=True)
                
                diff = difflib.unified_diff(
                    from_lines,
                    to_lines,
                    fromfile=f"a/{rel_path}",
                    tofile=f"b/{rel_path}"
                )
                
                diff_lines.extend(diff)
        
        return "".join(diff_lines)
    
    @staticmethod
    def apply_diff(workspace_path: Path, diff_path: Path) -> None:
        """Apply diff to workspace"""
        if not workspace_path.exists():
            raise FileNotFoundError(f"Workspace does not exist: {workspace_path}")
        if not workspace_path.is_dir():
            raise NotADirectoryError(f"Workspace is not a directory: {workspace_path}")
        if not diff_path.exists():
            raise FileNotFoundError(f"diff file does not exist: {diff_path}")
        
        patch_text = diff_path.read_text(encoding="utf-8")
        if not patch_text:
            return
        
        # Split multi-file diff
        file_sections = DiffProcessor._split_multi_file_diff(patch_text)

        for old_path, new_path, hunk_text in file_sections:
            target = (workspace_path / new_path).resolve()

            # Validate path safety
            if not FileManager.is_safe_path(workspace_path, target):
                raise ValueError(f"Suspicious path: {new_path}")

            # Handle deleted files
            if DiffProcessor._is_deleted_file( new_path, hunk_text):
                target = (workspace_path / old_path).resolve()
                if target.exists():
                    FileManager.safe_remove(target)
                    logger.info(f"Deleted file: {target}")
                continue

            # Handle new files
            if DiffProcessor._is_new_file(old_path, hunk_text):
                target.parent.mkdir(parents=True, exist_ok=True)
                new_content = "\n".join(
                    line[1:] for line in hunk_text.splitlines()
                    if line.startswith("+")
                )
                target.write_text(new_content, encoding="utf-8")
                logger.info(f"Created new file: {target}")
                continue

            # Modify existing file
            if not target.exists():
                raise FileNotFoundError(f"File to be modified does not exist: {target}")

            if target.is_dir():
                raise IsADirectoryError(f"Target path is a directory: {target}")

            target.parent.mkdir(parents=True, exist_ok=True)

            # Apply single file diff
            DiffProcessor._apply_single_file_diff(target, hunk_text)
            logger.info(f"Modified file: {target}")
    
    @staticmethod
    def _split_multi_file_diff(text: str) -> List[Tuple[str, str, str]]:
        """Split multi-file diff into individual file sections"""
        file_header_re = re.compile(r'^--- (?P<old>.*?)\s*\n^\+\+\+ (?P<new>.*?)\s*\n', re.M)
        matches = list(file_header_re.finditer(text))
        
        if not matches:
            print("No file headers found")
            return [("", "", "")]
        
        sections = []
        for i, m in enumerate(matches):
            old_path = m.group("old").replace("a/", "").strip()
            new_path = m.group("new").replace("b/", "").strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections.append((old_path, new_path, text[start:end]))
        
        return sections
    
    @staticmethod
    def _is_deleted_file(new_path: str, hunk_text: str) -> bool:
        """Check if file is deleted"""
        if new_path == "/dev/null":
            return True
        
        # Check hunk header
        for line in hunk_text.splitlines():
            if line.startswith("@@"):
                try:
                    m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
                    if m:
                        new_start = int(m.group(1))
                        new_cnt = int(m.group(2)) if m.group(2) else 1
                        return new_start == 0 and new_cnt == 0
                except (ValueError, IndexError):
                    continue
        return False
    
    @staticmethod
    def _is_new_file(old_path: str, hunk_text: str) -> bool:
        """Check if file is new"""
        if old_path == "/dev/null":
            return True
        
        # Check hunk header
        for line in hunk_text.splitlines():
            if line.startswith("@@"):
                try:
                    m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
                    if m:
                        old_start = int(m.group(1))
                        return old_start == 0
                except (ValueError, IndexError):
                    continue
        return False
    
    @staticmethod
    def _apply_single_file_diff(file_path: Path, hunk_text: str) -> None:
        """Apply single file diff"""
        if not file_path.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")
        
        # Check if binary file
        if DiffProcessor._is_binary_file(file_path):
            logger.warning(f"Skipping binary file: {file_path}")
            return
            
        source = file_path.read_text(encoding='utf-8').splitlines()
        result = []
        src_idx = 0
        current_hunk = None
        
        for line in hunk_text.splitlines():
            if line.startswith(("---", "+++")):
                continue
            
            if line.startswith("@@"):
                # Parse hunk header
                src_start, src_cnt = DiffProcessor._parse_hunk_header(line)
                
                # Keep leading unmodified lines
                while src_idx < src_start - 1:
                    if src_idx < len(source):
                        result.append(source[src_idx])
                    src_idx += 1
                current_hunk = line
                continue
            
            if not current_hunk or not line.startswith(("+", "-", " ")):
                continue
            
            tag, content = line[0], line[1:]
            if tag == " ":  # context line
                if src_idx < len(source):
                    result.append(source[src_idx])
                src_idx += 1
            elif tag == "-":  # deleted line
                src_idx += 1
            elif tag == "+":  # added line
                result.append(content)
        
        # Add remaining lines
        result.extend(source[src_idx:])
        
        # Write back to file
        file_path.write_text('\n'.join(result), encoding='utf-8')
    
    @staticmethod
    def _parse_hunk_header(line: str) -> tuple[int, int]:
        """Parse hunk header"""
        m = re.match(r"@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", line)
        if not m:
            raise ValueError(f"Cannot parse hunk header: {line}")
        start = int(m.group(1))
        cnt = int(m.group(2)) if m.group(2) else 1
        return start, cnt