import os
import json
import copy
import logging
import multiprocessing
import sys
import argparse
from pathlib import Path

import regex as re
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Dict, Any
from dataset.swe.processor import SWE_Processor
from install_cfuse import install
from utils.docker import Docker
from utils.cmd_utils import run_cmd
from utils.prompt_utils import prompt_format
from prompts import judge_scalar_prompt

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

def step(item):
    response = f"""Code Agent Generated Patch:
-----
<ai_patch>
{item['ai_patch']}
</ai_patch>
"""
    task = item['query']
    prompt = prompt_format(judge_scalar_prompt, task=task, response=response)
    return prompt


def post_process(response):
    def extract_pattern(text, pattern):
        pattern = re.compile(f'```{pattern}\s(.*?)```', re.DOTALL)
        # 查找所有匹配的内容\n
        matches = pattern.findall(text)
        return matches

    def extract_solution(solution_str, reward_fn):
        # TODO 抽取</think>tag之后的内容
        if not solution_str:
            return "0"

        # 查找</think>tag
        think_end = solution_str.find("</think>")
        if think_end != -1:
            solution_str = solution_str[think_end + len("</think>"):].strip()

        # 获取要提取的key
        index = reward_fn.find("cfuse/")
        if index != -1:
            reward_fn = reward_fn[index + len("cfuse/"):]

        matches = extract_pattern(solution_str, "json")
        if matches:
            try:
                match = json.loads(matches[-1])
                return str(match.get(reward_fn, "0"))
            except Exception as e:
                return str(solution_str)
        return str(solution_str)
    try:
        result_str = extract_solution(response, "scalar")
        return float(eval(result_str))
    except Exception as e:
        try:
            response = " ".join(response.split("\n"))
            result_str = extract_solution(response, "scalar")
            return float(eval(result_str))
        except Exception:
            raise RuntimeError(f"没有抽取到对应的deibase值")


def _process_single_item_task(item: Dict[str, Any], process_id: int, root: str, patch_root: str, file_name: str) -> Dict[str, Any]:
    """处理单个item的函数，在独立进程中执行"""
    docker = None
    instance_id = None
    try:
        instance_id = item['instance_id']
        logger.info(f"进程{process_id}: 开始处理 {instance_id} 文件 {file_name}")

        # 读取patch文件
        # 读取patch文件
        try:
            if file_name.endswith(".jsonl"):
                with open(os.path.join(patch_root, file_name), 'r', encoding='utf-8') as f:
                    file_json_content = f.readlines()
                lines = [line for line in [json.loads(line) for line in file_json_content] if
                         line["instance_id"] == instance_id]

                if not lines:
                    logger.info(f"进程{process_id}: {instance_id} 在 {file_name} 中没有patch数据，跳过")
                    return {
                        "original_index": item.get("original_index", 0),
                        "file_name": file_name,
                        "result": None
                    }
                patch_item = lines[0]
            elif file_name.endswith(".json"):
                with open(os.path.join(patch_root, file_name), 'r', encoding='utf-8') as f:
                    lines = json.load(f)
                if instance_id not in lines:
                    logger.info(f"进程{process_id}: {instance_id} 在 {file_name} 中没有patch数据，跳过")
                    return {
                        "original_index": item.get("original_index", 0),
                        "file_name": file_name,
                        "result": None
                    }
                patch_item = lines[instance_id]
        except FileNotFoundError:
            raise Exception(f"Patch文件不存在: {file_name}")
        except json.JSONDecodeError as e:
            raise Exception(f"Patch文件格式错误: {e}")

        if "model_patch" not in patch_item:
            raise Exception("Patch数据缺少model_patch字段")

        # 创建独立的Docker容器
        docker_name = os.getenv("DOCKER_NAME", "deibase_runner")
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
            # apply patch & prompt
            os.makedirs(os.path.join(root, instance_id), exist_ok=True)
            if file_name.endswith(".jsonl"):
                patch_file_name = file_name.replace(".jsonl", ".patch")
            elif file_name.endswith(".json"):
                patch_file_name = file_name.replace(".json", ".patch")
            patch_path = os.path.join(root, instance_id, patch_file_name)
            with open(patch_path, 'w', encoding='utf-8') as f:
                f.write(patch_item["model_patch"])
            # 复制patch到docker内
            run_cmd(
                cmd=f"docker cp {patch_path} {docker.container_name}:/workspace/logs/{instance_id}.patch",
                verbose=False
            )

            item_ = copy.deepcopy(item)
            item_["ai_patch"] = patch_item["model_patch"]
            prompt = step(item_)

            # 复制prompt到docker内
            if file_name.endswith(".jsonl"):
                prompt_file_name = file_name.replace(".jsonl", ".txt")
            elif file_name.endswith(".json"):
                prompt_file_name = file_name.replace(".json", ".txt")
            prompt_path = os.path.join(root, instance_id, prompt_file_name)
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
            # apply当前内容到仓库内部
            docker.exec_cmd(
                cmd=f"cd /testbed && git apply -v --reject /workspace/logs/{instance_id}.patch"
            )
        except Exception as e:
            print("GIT Apply 失败，但是没有关系")

        try:
            # 执行
            api_key = os.getenv('API-KEY', '')
            base_url = os.getenv('BASE-URL', '')
            model = os.getenv('MODEL', 'Kimi-K2-Instruct-0905')
            temperature = os.getenv("TEMPERATURE", "0")

            response_str = docker.exec_cmd(
                cmd=f"cd /testbed && conda run -n testbed /root/.local/bin/cfuse --temperature {temperature} --api-key {api_key} --base-url {base_url} --model {model} -pp /workspace/logs/{instance_id}.txt --logs-dir /workspace/logs/ --agent-file /workspace/logs/agent/code_judge_agent.md --yolo",
                verbose=True
            )
            # TODO 处理一下
            result = {
                "success": True,
                "scalar": post_process(response_str),
                "response_str": response_str
            }
        except Exception as e:
            raise Exception(f"任务执行过程出错: {e}")
            
        logger.info(f"进程{process_id}: 完成处理 {instance_id} 文件 {file_name}")

        return {
            "original_index": item.get("original_index", 0),
            "file_name": file_name,
            "result": result
        }

    except Exception as e:
        error_msg = f"进程{process_id}: 处理 {instance_id or item.get('instance_id', 'unknown')} 文件 {file_name} 时出错: {e}"
        logger.error(error_msg)
        return {
            "original_index": item.get("original_index", 0),
            "file_name": file_name,
            "result": {
                "msg": str(e),
                "success": False
            }
        }
    finally:
        # 清理临时目录
        try:
            docker.shutdown()
            if os.path.exists(os.path.join(root, instance_id, file_name)):
                os.remove(os.path.join(root, instance_id, file_name))

        except Exception as e:
            logger.warning(f"进程{process_id}: 清理临时目录时出错: {e}")


def run_batch_parallel(data: List[Dict[str, Any]], root: str, patch_root: str, files: List[str],
                       num_processes: int = None, save_interval: int = 5) -> None:
    """并行执行批处理任务

    Args:
        data: 评估数据列表
        root: 日志根目录
        patch_root: patch文件根目录
        files: patch文件名列表
        num_processes: 并行进程数，默认为CPU核心数
        save_interval: 每完成多少个任务后保存一次，默认为5
    """
    if num_processes is None:
        num_processes = multiprocessing.cpu_count()

    # 构建待处理任务列表
    pending_tasks = []
    for i, item in enumerate(data):
        if "deibase_result" not in item:
            item["deibase_result"] = [{"success": False, "file_name": file} for file in files]

        for deibase_item in item["deibase_result"]:
            if "success" in deibase_item and deibase_item["success"]:
                continue
            item_copy = copy.deepcopy(item)
            item_copy["original_index"] = i
            pending_tasks.append((item_copy, deibase_item["file_name"]))
    if not pending_tasks:
        logger.info("所有数据已处理完成")
        return

    total_pending = len(pending_tasks)
    logger.info(f"开始异步处理，共{total_pending}个任务，使用{num_processes}个进程，每{save_interval}个任务保存一次")

    # 使用进程池并行处理
    with ProcessPoolExecutor(max_workers=num_processes) as executor:
        # 提交所有任务
        future_to_task = {
            executor.submit(_process_single_item_task, item, idx, root, patch_root, file_name): (item, file_name)
            for idx, (item, file_name) in enumerate(pending_tasks)
        }

        # 收集结果
        completed = 0
        last_save_count = 0

        for future in as_completed(future_to_task):
            try:
                result = future.result()
                original_index = result["original_index"]
                file_name = result["file_name"]
                
                if result["result"] is not None:
                    for deibase_item in  data[original_index]["deibase_result"]:
                        if deibase_item["file_name"] == file_name:
                            deibase_item["success"] = result["result"].pop("success", False)
                            deibase_item["result"] = result["result"]
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
                item, file_name = future_to_task[future]
                logger.error(f"任务执行失败 - 实例ID: {item.get('instance_id', 'unknown')}, 文件: {file_name}, 错误: {e}")
                # 记录失败的任务信息
                original_index = item.get("original_index", 0)
                data[original_index]["result"][file_name] = {
                    "patch": "",
                    "msg": f"任务执行失败: {str(e)}",
                    "success": False
                }

    # 最终保存确保数据完整
    with open(os.path.join(root, "data.json"), "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logger.info("异步处理完成，结果已保存")

def is_finished(items, files):
    count = 0
    total_count = len(items) * len(files)
    for i, item in enumerate(items):
        if "deibase_result" in item:
            for deibase_item in item["deibase_result"]:
                if "success" in deibase_item and deibase_item["success"]:
                    count += 1
        else:
            item["deibase_result"] = [{"success": False, "file_name": file} for file in files]

    print(f"已经完成{count}条数据，剩余{total_count - count}条数据")
    return total_count - count > 0

def parse_args():
    parser = argparse.ArgumentParser(description='运行Deibase评估')
    
    # API配置参数
    parser.add_argument('--api-key', type=str, default="", help='API密钥，默认从环境变量API-KEY读取')
    parser.add_argument('--base-url', type=str, default="", help='基础URL，默认从环境变量BASE-URL读取')
    parser.add_argument('--model', type=str, default="Kimi-K2-Instruct", help='模型名称，默认从环境变量MODEL读取')
    parser.add_argument('--docker-name', type=str, default="deibase", help='docker name')
    parser.add_argument('--temperature', type=str, default="0", help='温度参数，默认从环境变量TEMPERATURE读取')
    
    # 路径配置参数
    parser.add_argument('--root', type=str, help='日志根目录，默认为当前目录下的log_deibase_模型名_时间戳')
    parser.add_argument('--patch-root', type=str, required=True, help='patch文件根目录')
    parser.add_argument('--data-path', type=str, required=True, help='原始数据路径，默认为SWE-Bench_Verified测试数据')
    parser.add_argument('--data-file', type=str, default="data.json", help='数据文件名，默认为data.json')

    # docker配置
    parser.add_argument('--docker-config-path', type=str, required=True, help='docker配置文件')
    
    # 进程配置参数
    parser.add_argument('--num-processes', type=int, default=multiprocessing.cpu_count(), help='并行进程数，默认为CPU核心数')
    parser.add_argument('--save-interval', type=int, default=5, help='每完成多少个任务后保存一次，默认为5')
    parser.add_argument('--instance_id', type=str, default=None, help='instance_id')
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    # 设置环境变量
    if args.api_key:
        os.environ["API-KEY"] = args.api_key
    if args.base_url:
        os.environ["BASE-URL"] = args.base_url
    if args.model:
        os.environ["MODEL"] = args.model
    if args.docker_name:
        os.environ["DOCKER_NAME"] = args.docker_name
    if args.temperature:
        os.environ["TEMPERATURE"] = str(args.temperature)
    
    # 设置默认路径
    if not args.root:
        import time
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        args.root = os.path.join(os.getcwd(), f"log_deibase_{args.model}_{timestamp}")
    

    # 创建目录
    os.makedirs(args.root, exist_ok=True)
    os.makedirs(os.path.join(args.root, "chat_history"), exist_ok=True)
    
    # 获取patch文件列表
    if not os.path.exists(args.patch_root):
        logger.error(f"patch根目录不存在: {args.patch_root}")
        exit(1)
    
    files = os.listdir(args.patch_root)
    files = [file for file in files if file.endswith(".jsonl") or file.endswith(".json")]
    files = [file for file in files if not file.startswith(".")]
    print(f"找到patch文件: {files}")

    # 加载或生成数据
    data_file_path = os.path.join(args.root, args.data_file)
    if os.path.exists(data_file_path):
        with open(data_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"从已存在的数据文件加载: {len(data)}条数据")
    else:
        if not os.path.exists(args.data_path):
            logger.error(f"原始数据文件不存在: {args.data_path}")
            exit(1)
        
        logger.info("处理原始数据文件...")
        data = SWE_Processor.process_swe_bench(path=args.data_path)
        with open(data_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logger.info(f"处理完成: {len(data)}条数据")

    if args.instance_id:
        data = [item for item in data if item["instance_id"] == args.instance_id]
        logger.info(f"过滤后数据量: {len(data)}")

    with open(args.docker_config_path, "r", encoding="utf-8") as f:
        docker_config = json.load(f)
    for i, item in enumerate(data):
        item["image_name"] = docker_config.get(item["instance_id"])

    # 使用并行模式运行
    retry_count = 0
    while is_finished(data, files) and retry_count < 10:
        run_batch_parallel(data=data, root=args.root, patch_root=args.patch_root, files=files,
                           num_processes=args.num_processes, save_interval=args.save_interval)
        retry_count += 1