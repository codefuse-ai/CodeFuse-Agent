import os
import glob
import json

def extract_trajectories(base_path):
    """提取给定路径下所有trajectory.jsonl文件的内容，优化输出结构"""
    trajectories = []

    # 获取基础路径的文件夹名称
    base_folder_name = os.path.basename(os.path.normpath(base_path))

    # 查找所有trajectory.jsonl文件
    pattern = os.path.join(base_path, "**/llm_messages.json")
    traj_files = glob.glob(pattern, recursive=True)

    def extract_instance_id(file_path, base_path):
        """从文件路径中提取instance_id，兼容两种格式"""
        relative_path = os.path.relpath(file_path, base_path)
        parts = relative_path.split(os.sep)

        # 从base_path往下一层就是instance_id
        # 兼容：
        # 1. django__django-17087/trajectory.jsonl
        # 2. django__django-17087/session_20251019_155858/trajectory.jsonl
        if parts:
            return parts[0]
        return None

    for traj_file in traj_files:
        instance_id = extract_instance_id(traj_file, base_path)

        try:
            with open(traj_file, 'r', encoding='utf-8') as f:
                # 读取所有行并解析JSON
                lines = f.readlines()
                traj_data = []
                for line in lines:
                    try:
                        traj_data.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue

                trajectories.append({
                    'id': base_folder_name,
                    'full_path': traj_file,
                    'instance_id': instance_id
                })

        except Exception as e:
            print(f"Error reading {traj_file}: {e}")

    return trajectories


def extract_pycfuse_trajectory(base_path):
    """提取给定路径下所有trajectory.jsonl文件的内容，优化输出结构"""
    trajectories = []
    # 查找所有trajectory.jsonl文件
    pattern = os.path.join(base_path, "**/llm_messages.json")
    traj_files = glob.glob(pattern, recursive=True)

    print(f"[提取轨迹] 在 {base_path} 中找到 {len(traj_files)} 个轨迹文件")

    def extract_instance_id(file_path, base_path):
        """从文件路径中提取instance_id，兼容两种格式"""
        relative_path = os.path.relpath(file_path, base_path)
        parts = relative_path.split(os.sep)

        # 从base_path往下一层就是instance_id
        # 兼容：
        # 1. django__django-17087/trajectory.jsonl
        # 2. django__django-17087/session_20251019_155858/trajectory.jsonl
        if parts:
            return parts[0]
        return None

    for idx, traj_file in enumerate(traj_files, 1):
        instance_id = extract_instance_id(traj_file, base_path)
        print(f"[提取轨迹] 处理第 {idx}/{len(traj_files)} 个文件: {instance_id}")

        try:
            with open(traj_file, 'r', encoding='utf-8') as f:
                # 读取所有行并解析JSON
                lines = f.readlines()
                traj_data = []
                for line in lines:
                    try:
                        traj_data.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue

                trajectories.append({
                    'full_path': traj_file,
                    'instance_id': instance_id
                })

        except Exception as e:
            print(f"Error reading {traj_file}: {e}")

    return trajectories


def get_debug_tool(traj, mode="pycfuse"):
    traj = traj["messages"]
    target_tool_calls = []
    for item in traj:
        if "tool_calls" in item and item["tool_calls"]:
            for tool_call in item["tool_calls"]:
                if "function" in tool_call and tool_call["function"] and tool_call["function"]["name"] in ["write_file",
                                                                                                           "edit_file"]:
                    target_tool_calls.append({
                        "tool_name": tool_call["function"]["name"],
                        "arguments": tool_call["function"]["arguments"],
                    })
    return target_tool_calls


def get_write_tool(traj, mode="pycc"):
    target_tool_calls = []

    for item in traj:
        if mode == "pycc":
            if "content" not in item:
                continue
            item_contents = item["content"]
            for item_content in item_contents:
                if "name" in item_content and "input" in item_content and item_content["name"] in ["Edit", "Write"]:
                    target_tool_calls.append({
                        "tool_name": item_content["name"],
                        "arguments": item_content["input"],
                    })
        elif mode == "pycfuse":
            if "event_type" in item and item["event_type"] == "tool_result" and "tool_name" in item and item[
                "tool_name"] in ["write_file", "edit_file"]:
                target_tool_calls.append({
                    "tool_name": item["tool_name"],
                    "arguments": item["arguments"]
                })
    return target_tool_calls


def to_string(traj, idx=0):
    traj_str = ""
    for item in traj:
        traj_str += f"\t<tool_call name=\"{item['tool_name']}\">\n\t\t<arguments>\n\t\t\t{item['arguments']}\n\t\t</arguments>\n\t</tool_call>\n"

    return f"<trajectory idx='{idx}'>\n{traj_str}</trajectory>"

