#!/usr/bin/env python3
"""
分析tree.json文件，只计算从根节点到叶节点的完整路径
并提取model_beam文件对应的路径
"""
import shutil

import json
import os
import glob
from collections import defaultdict
from fractions import Fraction
from pathlib import Path


def build_tree_structure(data):
    """构建树结构，建立节点映射"""
    node_map = {}
    for node in data['nodes']:
        node_map[node['commit_id']] = node
    return node_map


def find_all_root_to_leaf_paths(node_map, root_commits):
    """找到从根节点到所有叶节点的完整路径"""
    all_paths = []

    def dfs(current_commit_id, current_path):
        current_path.append(current_commit_id)
        current_node = node_map[current_commit_id]
        children = current_node.get('children', [])
        if not children:
            all_paths.append(current_path.copy())
        else:
            # 递归处理所有子节点
            for child_id in children:
                dfs(child_id, current_path)

        current_path.pop()

    # 从根节点开始搜索
    for root_commit in root_commits:
        dfs(root_commit, [])

    return all_paths


def extract_model_beam_identifiers(project_path):
    """
    提取指定路径下所有以model_beam_开头的文件名中的标识符
    例如：model_beam_step_72_index_5_17633774 -> beam_step_72_index_5_17633774

    Args:
        project_path: 项目路径，如 '/Users/jiawan/Desktop/all_archives/astropy__astropy-13033'

    Returns:
        set: 包含所有标识符的集合（与tree.json中的节点格式匹配）
    """
    identifiers = set()
    pattern = os.path.join(project_path, "model_beam_*")
    model_files = glob.glob(pattern)

    for file_path in model_files:
        filename = os.path.basename(file_path)
        if filename.startswith("model_beam_"):
            identifier = filename.replace("model_beam_", "beam_", 1)
            identifiers.add(identifier)

    return identifiers


def filter_paths_by_end_nodes(all_paths, target_end_nodes):
    """
    筛选出路径末尾节点在目标集合中的路径

    Args:
        all_paths: 所有从根到叶的路径列表
        target_end_nodes: 目标末尾节点集合

    Returns:
        list: 筛选后的路径列表
    """
    filtered_paths = []
    for path in all_paths:
        if path and path[-1] in target_end_nodes:
            filtered_paths.append(path)
    copy_target_end_nodes = []
    if len(target_end_nodes) > len(filtered_paths):
        le = min(len(target_end_nodes) - len(filtered_paths), len(all_paths))
        all_paths.sort(key=len, reverse=True)  # 最长路径在前
        for i in range(le):
            try:
                if all_paths[i] not in filtered_paths:
                    filtered_paths.append(all_paths[i])
                    copy_target_end_nodes.append(all_paths[i][-1])
            except Exception as e:
                print(e)
    return filtered_paths


def analyze_project_model_beam_paths(project_name):
    """
    分析指定项目的model_beam路径并计算reward值

    Args:
        project_name: 项目名称，如 'astropy__astropy-13033'

    Returns:
        dict: 包含分析结果和reward值的字典
    """
    project_path = f"{project_name}"
    pattern = os.path.join(project_path, "testbed", "session_*", "beam_search", "testbed", "git_tree", "tree.json")
    tree_files = glob.glob(pattern)
    if not tree_files:
        print(f"未找到 {project_name} 的tree.json文件")
        return None

    file_path = tree_files[0]
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"读取文件失败: {e}")
        return None
    node_map = build_tree_structure(data)
    try:
        all_paths = find_all_root_to_leaf_paths(node_map, data['root_commits'])
    except Exception as e:
        print(f"构建树结构失败: {e}")
        raise Exception(f"构建树结构失败: {e}")
    model_beam_identifiers = extract_model_beam_identifiers(project_path)
    if model_beam_identifiers:
        filtered_paths = filter_paths_by_end_nodes(all_paths, model_beam_identifiers)
        return {
            'project_name': project_name,
            'total_paths': len(all_paths),
            'model_beam_identifiers': model_beam_identifiers,
            'matched_paths': filtered_paths,
            'all_paths': all_paths,
        }
    else:
        print(f"未找到 {project_name} 的model_beam标识符")
        return ""


def load_chat_histories(project_name, matched_paths=[]):
    """
    加载chat_history文件，构建节点到chat_history的映射
    Args:
        project_name: 项目名称
    Returns:
        dict: key为节点ID（去掉_chat.json后缀的文件名），value为chat_history内容
    """

    session_dirs = glob.glob(
        f"{project_name}/testbed/session_*"
    )
    session_root = session_dirs[0]
    chat_dir = os.path.join(session_root, "beam_search/testbed/git_tree/chat_histories")

    # 遍历所有chat_history文件
    chat_histories_dicts = {}
    for matched_path in matched_paths:
        chat_histories = []
        for node_id in matched_path:
            file = node_id + "_chat.json"
            chat_file = os.path.join(chat_dir, file)
            if os.path.isfile(chat_file):
                with open(chat_file, 'r', encoding='utf-8') as f:
                    chat_content = json.load(f)
                    chat_histories.extend(chat_content)
        chat_histories_dicts[matched_path[-1]] = chat_histories
    return chat_histories_dicts


def create_data(project_name="astropy__astropy-12907-15min-1hour"):
    result = analyze_project_model_beam_paths(project_name)

    if result:
        result["chat_history"] = load_chat_histories(project_name, matched_paths=result["matched_paths"])
        chat_history = result["chat_history"].copy()
        return chat_history
    else:
        return None
def write_data(submitted_file, project_path):
    project_path_new = str(Path(project_path).parent)
    deal_file = []
    for name in deal_file:
        full_path = os.path.join(project_path, name)
        pattern = os.path.join(full_path, "testbed", "session_*", "llm_messages.json")
        llm_messages = glob.glob(pattern)
        with open(llm_messages[0], 'r', encoding='utf-8') as f:
            llm_messages_data = json.load(f)
        llm_messages_data_r = llm_messages_data.copy()
        if os.path.isdir(full_path):
            data_res = create_data(full_path)
            if data_res:
                index = 0
                new_path_llms = []
                pattern = os.path.join(full_path, "model_beam*")
                model_files = glob.glob(pattern)
                for node in data_res:
                    new_path = os.path.join(project_path_new, f"{submitted_file}{index}", name)
                    os.makedirs(new_path, exist_ok=True)
                    path_patch = f"{model_files[index_llm]}"
                    path_patch_new = os.path.join(new_path, f"model.patch")
                    shutil.copy2(path_patch, path_patch_new)
                    llm_messages_data_r["messages"] = data_res[node]
                    new_path_llm = os.path.join(new_path, "llm_messages.json")
                    with open(new_path_llm, 'w', encoding='utf-8') as f_out:
                        json.dump(llm_messages_data_r, f_out, ensure_ascii=False)
                    new_path_llms.append(new_path_llm)
                    index += 1
            else:
                print(f"未找到 {full_path} ")
        else:
            print(f"{full_path} 不是文件夹")
if __name__ == "__main__":
    submitted_file = ""
    project_path = ""
    write_data(submitted_file, project_path)
    print("end")







