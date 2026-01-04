import os
import glob
import json
import csv
import pandas as pd
from typing import List, Dict, Any, Union


class Preprocessor:

    @staticmethod
    def load_data(path: Union[str, List[str]], file_format: str = None, folder_pattern: str = None) -> List[
        Dict[str, Any]]:
        """
        通用数据加载函数，支持多种格式

        Args:
            path: 文件路径、文件夹路径或文件路径列表
            file_format: 文件格式，可选值：'jsonl', 'json', 'csv', 'parquet'。
                        如果为None，则根据文件扩展名自动判断
            folder_pattern: 文件夹名称的过滤模式，支持通配符匹配。
                           例如：'train*' 匹配所有以train开头的文件夹

        Returns:
            List[Dict[str, Any]]: 统一返回list of dict格式
        """
        if isinstance(path, (list, tuple)):
            all_data = []
            for p in path:
                all_data.extend(Preprocessor._load_single_path(p, file_format, folder_pattern))
            return all_data

        return Preprocessor._load_single_path(path, file_format, folder_pattern)

    @staticmethod
    def _load_single_path(path: str, file_format: str = None, folder_pattern: str = None) -> List[Dict[str, Any]]:
        """加载单个路径（文件或文件夹）"""
        import fnmatch

        if not os.path.exists(path):
            raise FileNotFoundError(f"路径不存在: {path}")

        # 如果是文件夹，递归查找所有支持的文件
        if os.path.isdir(path):
            all_data = []
            supported_formats = ['jsonl', 'json', 'csv', 'parquet']

            # 如果指定了特定格式，只查找该格式
            if file_format and file_format in supported_formats:
                patterns = [os.path.join(path, "**", f"*.{file_format}")]
            else:
                patterns = [os.path.join(path, "**", f"*.{fmt}") for fmt in supported_formats]

            files = []
            for pattern in patterns:
                files.extend(glob.glob(pattern, recursive=True))

            # 如果指定了文件夹过滤模式，过滤文件路径
            if folder_pattern:
                filtered_files = []
                for file in files:
                    # 检查文件完整路径是否匹配过滤模式（过滤掉匹配的文件）
                    if not fnmatch.fnmatch(file, folder_pattern):
                        filtered_files.append(file)
                files = filtered_files

            for file in files:
                try:
                    fmt = file_format or os.path.splitext(file)[1].lower().lstrip('.')
                    all_data.extend(Preprocessor._load_single_file(file, fmt))
                except Exception as e:
                    print(f"警告：跳过文件 {file}，原因：{str(e)}")
            return all_data

        # 如果是单个文件
        return Preprocessor._load_single_file(path, file_format)

    @staticmethod
    def _load_single_file(file_path: str, file_format: str = None) -> List[Dict[str, Any]]:
        """加载单个文件"""
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 如果未指定格式，根据扩展名判断
        if file_format is None:
            file_format = os.path.splitext(file_path)[1].lower().lstrip('.')

        file_format = file_format.lower()

        try:
            if file_format == 'jsonl':
                return Preprocessor._load_jsonl(file_path)
            elif file_format == 'json':
                return Preprocessor._load_json(file_path)
            elif file_format == 'csv':
                return Preprocessor._load_csv(file_path)
            elif file_format == 'parquet':
                return Preprocessor._load_parquet(file_path)
            else:
                raise ValueError(f"不支持的文件格式: {file_format}")
        except Exception as e:
            raise RuntimeError(f"加载文件失败 {file_path}: {str(e)}")

    @staticmethod
    def _load_jsonl(file_path: str) -> List[Dict[str, Any]]:
        """加载jsonl格式文件"""
        data = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        raise ValueError(f"JSON解析错误 文件:{file_path} 行:{line_num} - {str(e)}")
        return data

    @staticmethod
    def _load_json(file_path: str) -> List[Dict[str, Any]]:
        """加载json格式文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = json.load(f)

        # 支持两种json格式：list of dict 或 dict
        if isinstance(content, list):
            return content
        elif isinstance(content, dict):
            return [content]
        else:
            raise ValueError("JSON文件内容必须是dict或list of dict格式")

    @staticmethod
    def _load_csv(file_path: str) -> List[Dict[str, Any]]:
        """加载csv格式文件"""
        data = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, 1):
                try:
                    data.append(dict(row))
                except Exception as e:
                    raise ValueError(f"CSV解析错误 文件:{file_path} 行:{row_num + 1} - {str(e)}")
        return data

    @staticmethod
    def _load_parquet(file_path: str) -> List[Dict[str, Any]]:
        """加载parquet格式文件"""
        try:
            df = pd.read_parquet(file_path)
            return df.to_dict('records')
        except Exception as e:
            raise ValueError(f"Parquet文件读取失败: {str(e)}")