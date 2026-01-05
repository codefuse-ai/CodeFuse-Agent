import os
import json
import copy
import logging
import multiprocessing
import argparse
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Any

from install_cfuse import install
from utils.docker import Docker
from utils.cmd_utils import run_cmd
from prompts import judge_extract_test_case_prompt, test_content_prompt
from utils.traj_utils import extract_trajectories, get_debug_tool, to_string
from utils.prompt_utils import prompt_format
from dataset.swe.processor import SWE_Processor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

current_file = Path(__file__).resolve()


def step(current_item, trajectory_root, dir_files, test_content=""):
    query = current_item["query"]
    traj_str = ""

    if test_content:
        current_test_case = test_content_prompt
    else:
        current_test_case = ""

    for i, file in enumerate(dir_files):
        current_path = os.path.join(trajectory_root, file)
        if file.startswith("pycc"):
            mode = "pycc"
        elif file.startswith("pycfuse"):
            mode = "pycfuse"
        else:
            continue

        # 确保路径是绝对路径
        if not os.path.isabs(current_path):
            current_path = os.path.join(os.path.dirname(__file__), current_path)

        # 提取轨迹数据
        trajectories = extract_trajectories(current_path)
        trajectories = [item for item in trajectories if item["instance_id"] == current_item["instance_id"]]
        for trajectory in trajectories:
            with open(trajectory["full_path"], "r", encoding="utf-8") as f:
                lines = json.load(f)
            target_tools = get_debug_tool(lines, mode=mode)
            traj_str += to_string(target_tools, idx=i + 1) + "\n"

    return prompt_format(judge_extract_test_case_prompt, task=query, trajectories=traj_str, current_test_case=current_test_case)


def _process_single_item_task(item: Dict[str, Any], process_id: int, root: str, traj_root:str, files: list, test_content:str="", current_idx=0) -> Dict[str, Any]:
    logger.info(f"Processing 进程{process_id}，处理{'、'.join(files)}这几条轨迹")
    """处理单个item的函数，在独立进程中执行"""
    docker = None
    instance_id = None
    try:
        instance_id = item['instance_id']
        logger.info(f"进程{process_id}: 开始处理 {instance_id}")

        docker_name = os.getenv("DOCKER_NAME", "test_case_generator")

        # 创建独立的Docker容器
        docker = Docker(
            image_name=item["image_name"],
            container_name=f"{instance_id}_{docker_name}_{process_id}"
        )

        # step1 启动容器
        success = docker.run()
        if not success:
            raise Exception("Docker容器启动失败")

        # step2 拉取脚手架代码，并安装依赖
        try:
            install(
                docker=docker,
                package_path=str(current_file.parent.parent)
            )

            instance_root = os.path.join(root, instance_id)
            os.makedirs(instance_root, exist_ok=True)
            test_case_result_root = os.path.join(instance_root, "test_case_extract_result")

            if test_content:
                test_path = os.path.join(root, instance_id, "test_current_issue.py")
                with open(test_path, "w", encoding="utf-8") as f:
                    f.write(test_content)
                run_cmd(
                    cmd=f"docker cp {test_path} {docker.container_name}:/testbed/test_current_issue.py",
                    verbose=False
                )

            prompt = step(item, traj_root, files, test_content)
            prompt_path = os.path.join(root, instance_id, "prompt.txt")
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write(prompt)
            run_cmd(
                cmd=f"docker cp {prompt_path} {docker.container_name}:/workspace/logs/{instance_id}.txt",
                verbose=False
            )
            run_cmd(
                cmd=f"docker cp {os.getcwd()}/config/agent {docker.container_name}:/workspace/logs/",
                verbose=False
            )
        except Exception as e:
            raise Exception(f"环境准备失败: {e}")

        try:
            # 执行
            model = os.getenv('MODEL', "Kimi-K2-Instruct")
            api_key = os.getenv('API-KEY', "")
            base_url = os.getenv("BASE-URL", "")
            temperature = os.getenv("TEMPERATURE", "0")

            docker.exec_cmd(
                cmd=f"cd /testbed && conda run -n testbed /root/.local/bin/cfuse --temperature {temperature} --api-key {api_key} --base-url {base_url} --model {model} -pp /workspace/logs/{instance_id}.txt --logs-dir /workspace/logs/ --agent-file /workspace/logs/agent/code_judge_agent.md --yolo",
                verbose=True
            )
            file_content = docker.exec_cmd(
                cmd="cd /testbed && cat test_current_issue.py"
            )
            if "cat: test_current_issue.py: No such file or directory" in file_content:
                raise RuntimeError(f"No such file or directory test_current_issue.py")

            if not file_content:
                raise RuntimeError(f"No test file content found")

            # 提取当前的extract_test_case_trajectory结果到外面
            os.makedirs(f"{test_case_result_root}/{current_idx}", exist_ok=True)
            run_cmd(
                cmd=f"docker cp {docker.container_name}:/workspace/logs/testbed/ {test_case_result_root}/{current_idx}/"
            )

            logger.info(f"进程{process_id}: 完成处理 {instance_id}")

            return {
                "original_index": item.get("original_index", 0),
                "result": {
                    "test_file_content": file_content,
                    "msg": "",
                    "success": True
                }
            }
        except Exception as e:
            raise Exception(f"任务执行过程出错: {e}")

    except Exception as e:
        error_msg = f"进程{process_id}: 处理 {instance_id or item.get('instance_id', 'unknown')} 时出错: {e}"
        logger.error(error_msg)
        return {
            "original_index": item.get("original_index", 0),
            "result": {
                "msg": str(e),
                "success": False
            }
        }
    finally:
        # 清理Docker容器
        docker.shutdown()


def process_single(item: Dict[str, Any], process_id: int, root: str, traj_root: str, window_size=2):
    files = os.listdir(traj_root)
    files = [file for file in files if os.path.isdir(os.path.join(traj_root, file))]
    start_idx, end_idx = 0, window_size
    test_file_content = ""
    log = []
    success = True

    window_idx = 0
    while start_idx < len(files):
        current_files = files[start_idx:min(end_idx, len(files))]
        response = _process_single_item_task(item=item, process_id=process_id, root=root, traj_root=traj_root, files=current_files, test_content=test_file_content, current_idx=window_idx)
        if response["result"]["success"] and "test_file_content" in response["result"]:
            test_file_content = response["result"]["test_file_content"]
            log.append(
                {"start_idx": start_idx, "end_idx": end_idx, "files": current_files, "test_file_content": test_file_content}
            )
        else:
            success = False
            log.append(
                {"start_idx": start_idx, "end_idx": end_idx, "files": current_files}
            )
            break
        start_idx, end_idx = end_idx, end_idx + window_size
        window_idx += 1

    with open(os.path.join(root, item["instance_id"], "test_case_log.json"), "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=4)

    return {
        "original_index": item["original_index"],
        "result": {
            "success": success,
            "test_file_content": test_file_content
        }
    }


def run_batch_parallel(data: List[Dict[str, Any]], root: str, traj_root: str, window_size=2,
                       num_processes: int = None, save_interval: int = 5) -> None:
    """并行执行批处理任务

    Args:
        data: 评估数据列表
        root: 日志根目录
        traj_root: 轨迹文件根目录
        num_processes: 并行进程数，默认为CPU核心数
        save_interval: 每完成多少个任务后保存一次，默认为5
    """
    if num_processes is None:
        num_processes = multiprocessing.cpu_count()

    # 构建待处理任务列表
    pending_tasks = []
    for i, item in enumerate(data):
        if not ("test_file_content" in item and item["test_file_content"]):
            item_copy = copy.deepcopy(item)
            item_copy["original_index"] = i
            pending_tasks.append(item_copy)

    if not pending_tasks:
        logger.info("所有数据已处理完成")
        return

    total_pending = len(pending_tasks)
    logger.info(f"开始异步处理，共{total_pending}个任务，使用{num_processes}个进程，每{save_interval}个任务保存一次")

    # 使用进程池并行处理
    with ProcessPoolExecutor(max_workers=num_processes) as executor:
        # 提交所有任务
        future_to_task = {
            executor.submit(process_single, item, idx, root, traj_root, window_size): item
            for idx, item in enumerate(pending_tasks)
        }

        # 收集结果
        completed = 0
        last_save_count = 0

        for future in as_completed(future_to_task):
            try:
                result = future.result()
                original_index = result["original_index"]
                
                if result["result"] is not None:
                    data[original_index]["test_file_content"] = result["result"].get("test_file_content")
                    if "result" not in data[original_index]:
                        data[original_index]["result"] = {}
                    data[original_index]["result"]["success"] = result["result"].get("success")

                completed += 1

                # 计算预估剩余时间
                import time
                if completed == 1:
                    start_time = time.time()
                    elapsed_time = 0
                    estimated_total_time = 0
                    remaining_time_str = "计算中..."
                else:
                    elapsed_time = time.time() - start_time
                    estimated_total_time = elapsed_time / completed * total_pending
                    remaining_time = estimated_total_time - elapsed_time

                    # 格式化剩余时间
                    if remaining_time < 60:
                        remaining_time_str = f"{remaining_time:.0f}秒"
                    elif remaining_time < 3600:
                        remaining_time_str = f"{remaining_time / 60:.1f}分钟"
                    else:
                        remaining_time_str = f"{remaining_time / 3600:.1f}小时"

                logger.info(
                    f"异步处理进度: {completed}/{total_pending} ({completed / total_pending * 100:.1f}%) - 预估剩余时间: {remaining_time_str}")

                # 定时保存机制
                if completed - last_save_count >= save_interval or completed == total_pending:
                    with open(os.path.join(root, "data.json"), "w", encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=4)
                    last_save_count = completed
                    logger.info(f"已保存进度: {completed}/{total_pending}")

            except Exception as e:
                item = future_to_task[future]
                logger.error(f"任务执行失败 - 实例ID: {item.get('instance_id', 'unknown')}, 错误: {e}")
                # 记录失败的任务信息
                original_index = item.get("original_index", 0)
                if "result" not in data[original_index]:
                    data[original_index]["result"] = {}
                data[original_index]["result"] = {
                    "msg": str(e),
                    "success": False
                }

    # 最终保存确保数据完整
    with open(os.path.join(root, "data.json"), "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logger.info("异步处理完成，结果已保存")


def is_finished(data):
    """检查是否还有未处理的数据"""
    count = 0
    total_count = len(data)
    for item in data:
        if "test_file_content" in item and item["test_file_content"]:
            count += 1

    print(f"已经完成{count}条数据，剩余{total_count - count}条数据")
    return total_count - count > 0


def parse_args():
    parser = argparse.ArgumentParser(description='提取测试用例')
    
    # API配置参数
    parser.add_argument('--api-key', type=str, default=os.getenv('API-KEY', ''),
                        help='API密钥，默认从环境变量API-KEY读取')
    parser.add_argument('--base-url', type=str, default=os.getenv('BASE-URL', ''),
                        help='基础URL，默认从环境变量BASE-URL读取')
    parser.add_argument('--model', type=str, default=os.getenv('MODEL', 'Kimi-K2-Instruct'),
                        help='模型名称，默认从环境变量MODEL读取')
    parser.add_argument('--temperature', type=float, default=float(os.getenv('TEMPERATURE', '0')),
                        help='温度参数，默认从环境变量TEMPERATURE读取')
    parser.add_argument('--docker_name', type=str, default="test_case_generator",
                        help='温度参数，默认从环境变量TEMPERATURE读取')
    
    # 路径配置参数
    parser.add_argument('--traj-root', type=str, required=True,
                        help='轨迹文件根目录')
    parser.add_argument('--data-path', type=str, default="./SWE-Bench_Verified/test-00000-of-00001.parquet",
                        help='原始数据路径，默认为SWE-Bench_Verified测试数据')
    parser.add_argument('--root', type=str, default=os.path.join(os.getcwd(), "0.2.0_k2-tts_4_test_case_20251209"),
                        help='日志根目录，默认为当前目录下的cfuse_0.2.0_k2-tts_4_test_case_20251209')
    parser.add_argument('--data-file', type=str, default="data.json",
                        help='数据文件名，默认为data.json')

    # docker配置
    parser.add_argument('--docker-config-path', type=str, required=True, help='docker配置文件')

    # 进程配置参数
    parser.add_argument('--window-size', type=int, default=2,
                        help='窗口大小，默认为2')
    parser.add_argument('--num-processes', type=int, default=multiprocessing.cpu_count(),
                        help='并行进程数，默认为CPU核心数')
    parser.add_argument('--save-interval', type=int, default=5,
                        help='每完成多少个任务后保存一次，默认为5')
    
    # 过滤参数
    parser.add_argument('--use-existing-data', action='store_true',
                        help='使用已存在的data.json文件，不重新加载原始数据')
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    # 设置环境变量
    os.environ["API-KEY"] = args.api_key
    os.environ["BASE-URL"] = args.base_url
    os.environ["MODEL"] = args.model
    os.environ["TEMPERATURE"] = str(args.temperature)

    if args.docker_name:
        os.environ["DOCKER_NAME"] = args.docker_name

    # 创建目录
    os.makedirs(args.root, exist_ok=True)

    # 加载或生成数据
    data_file_path = os.path.join(args.root, args.data_file)
    
    if args.use_existing_data and os.path.exists(data_file_path):
        logger.info(f"使用已存在的数据文件: {data_file_path}")
        with open(data_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        if not os.path.exists(args.data_path):
            logger.error(f"原始数据文件不存在: {args.data_path}")
            exit(1)
            
        logger.info(f"从原始数据加载: {args.data_path}")
        data = SWE_Processor.process_swe_bench(path=args.data_path)
        with open(data_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    with open(args.docker_config_path, "r", encoding="utf-8") as f:
        docker_config = json.load(f)

    for i, item in enumerate(data):
        item["image_name"] = docker_config.get(item["instance_id"])

    retry_count = 0
    # 使用并行模式运行, 最大重试10次
    while is_finished(data) and retry_count < 10:
        run_batch_parallel(data=data, root=args.root, traj_root=args.traj_root, window_size=args.window_size,
                           num_processes=args.num_processes, save_interval=args.save_interval)
        retry_count += 1