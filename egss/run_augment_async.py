import json
import logging
import multiprocessing
import copy
import os
import argparse
import regex as re
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Dict, Any
from prompts import judge_preference_prompt, judge_trae_selector_prompt
from utils.docker import Docker
from utils.prompt_utils import prompt_format
from utils.cmd_utils import run_cmd
from utils.git_utils import filter_diff

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


def deibase_lambda(x):
    if "result" in x and "scalar" in x["result"] and x["result"]["scalar"] is not None:
        return x["result"]["scalar"]
    return -float("inf")


def test_case_lambda(x):
    if "result" in x and "passed" in x["result"] and "total" in x["result"] and x["result"]["total"] > 0:
        return x["result"]["passed"] / x["result"]["total"], x.get("scalar", 0)
    return -float("inf"), x.get("scalar", 0)


def step(item, patch_root, instance_id, top_k, model_config):
    alpha2id = {
        "1": "A", "2": "B", "3": "C", "4": "D", "5": "E", "6": "F", "7": "G", "8": "H", "9": "I", "10": "J", "11": "K",
        "12": "L", "13": "M"
    }
    # 先采集candidate patch
    if "deibase_result" in item:
        # 如果scalar等于0，就没必要再去比较了
        deibase = [x for x in item["deibase_result"] if "result" in x and x["result"] and "scalar" in x["result"] and x["result"]["scalar"] > 0.3]
        files = [x["file_name"] for x in deibase[:top_k]]
    elif "test_case_result" in item:
        # 过滤掉一些passed为0的脏数据，这些数据没必要参与比较
        test_case_result = item["test_case_result"]
        # test_case_result = [x for x in test_case_result if "result" in x and x["result"] and "total" in x["result"] and x["result"]["total"] > 0 and x["result"]["passed"] / x["result"]["total"] > 0]
        test_case_result = [x for x in test_case_result if x.get("scalar", 0) > 0.3]
        print(f"{item['instance_id']}: 最后留下{len(test_case_result)}个用例用于筛选")
        files = [x["file_name"] for x in test_case_result[:top_k]]
    else:
        raise RuntimeError(f"没有识别到任何的策略 - deibase/test_case_result")

    responses = ""
    candidate_patches_id2patch = {}
    for i, file_name in enumerate(files):
        try:
            if file_name.endswith(".jsonl"):
                with open(os.path.join(patch_root, file_name), 'r', encoding='utf-8') as f:
                    file_json_content = f.readlines()
                lines = [line for line in [json.loads(line) for line in file_json_content] if
                         line["instance_id"] == instance_id]
                if not lines:
                    logger.warning(f"实例 {instance_id} 在文件 {file_name} 中没有找到patch数据")
                    continue

                patch = filter_diff(lines[0]["model_patch"])

            elif file_name.endswith(".json"):
                with open(os.path.join(patch_root, file_name), 'r', encoding='utf-8') as f:
                    lines = json.load(f)
                if instance_id not in lines:
                    logger.warning(f"实例 {instance_id} 在文件 {file_name} 中没有找到patch数据")
                    continue
                patch = filter_diff(lines[instance_id]["model_patch"])

            alphaid = alpha2id[str(i + 1)]
            candidate_patches_id2patch[alphaid] = file_name
            responses += f"<patch id='{alphaid}'>\n{patch}\n</patch>"
        except Exception as e:
            logger.error(f"处理文件 {file_name} 时出错: {e}")
            continue

    task = item['query']
    if model_config.get("prompt", "judge_trae_selector_prompt") == "judge_trae_selector_prompt":
        prompt = prompt_format(judge_trae_selector_prompt, task=task, responses=responses)
    else:
        prompt = prompt_format(judge_preference_prompt, task=task, responses=responses)

    return prompt, candidate_patches_id2patch


def post_process(response):
    def extract_pattern(text, pattern):
        pattern = re.compile(f'```{pattern}\s(.*?)```', re.DOTALL)
        # 查找所有匹配的内容\n
        matches = pattern.findall(text)
        return matches

    def extract_solution(solution_str, reward_fn):
        # TODO 抽取</think>tag之后的内容
        if not solution_str:
            return None

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
                return match[reward_fn]
            except Exception as e:
                return solution_str
        return solution_str

    try:
        return extract_solution(response, "result")
    except Exception as e:
        response = " ".join(response.split("\n"))
        return extract_solution(response, "result")


def _process_single_augment_task(item: Dict[str, Any], process_id: int, root: str, patch_root: str, attempt_idx: int,
                                 top_k: int, model_config: dict) -> Dict[str, Any]:
    """处理单个augment任务的函数，在独立进程中执行"""
    docker = None
    instance_id = None
    try:
        instance_id = item['instance_id']
        logger.info(f"进程{process_id}: 开始处理 {instance_id} 第{attempt_idx}次尝试")

        # 创建独立的Docker容器
        docker_name = os.getenv("DOCKER-NAME", "augment_runner")
        docker = Docker(
            image_name=f"reg.antgroup-inc.cn/swe-bench-image/{instance_id}",
            container_name=f"{instance_id}_{docker_name}_{process_id}"
        )

        # step1 启动容器
        success = docker.run()
        if not success:
            raise Exception("Docker容器启动失败")

        # step2 拉取脚手架代码，并安装依赖
        try:
            pycfuse_package = "pycfuse-0.3.6-py3-none-any.whl"
            docker.exec_cmd(
                cmd=f"wget -P /tmp https://artifacts.antgroup-inc.cn/artifact/repositories/simple-dev/pycfuse/{pycfuse_package}",
                verbose=False
            )
            docker.exec_cmd(
                cmd=f"pipx install /tmp/{pycfuse_package}",
                verbose=False
            )
            docker.exec_cmd(
                cmd="mkdir -p /workspace/logs",
                verbose=False
            )

            prompt, candidate_patches_id2patch = step(item, patch_root=patch_root, instance_id=instance_id, top_k=top_k, model_config=model_config)

            if len(candidate_patches_id2patch) == 1:
                return {
                    "original_index": item.get("original_index", 0),
                    "attempt_index": attempt_idx,
                    "result": {"success": True, "msg": "只有唯一的一个patch", "patch_id": list(candidate_patches_id2patch.values())[0]},
                    "success": True
                }
            elif len(candidate_patches_id2patch) == 0:
                return {
                    "original_index": item.get("original_index", 0),
                    "attempt_index": attempt_idx,
                    "result": {"success": True, "msg": "没有patch"},
                    "success": True
                }

            instance_root = os.path.join(root, instance_id)
            os.makedirs(instance_root, exist_ok=True)
            augment_log_root = os.path.join(instance_root, "augment_output", f"attempt_{attempt_idx}")
            os.makedirs(augment_log_root, exist_ok=True)

            prompt_path = os.path.join(instance_root, f"attempt_{attempt_idx}.txt")
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
            model = model_config.get("model", os.getenv('MODEL', "Kimi-K2-Instruct"))
            api_key = model_config["api_key"]
            base_url = model_config["base_url"]
            temperature = model_config.get("temperature", "1")

            response_str = docker.exec_cmd(
                cmd=f"cd /testbed && conda run -n testbed /root/.local/bin/pycfuse --temperature {temperature} --api-key {api_key} --base-url {base_url} --model {model} -pp /workspace/logs/{instance_id}.txt --logs-dir /workspace/logs/ --agent-file /workspace/logs/agent/code_judge_agent.md --yolo",
                verbose=True
            )

            aug_result = {
                "patch_id": candidate_patches_id2patch[post_process(response_str)],
                "success": True
            }

        except Exception as e:
            raise Exception(f"任务执行过程出错: {e}")

        try:
            run_cmd(
                cmd=f"docker cp {docker.container_name}:/workspace/logs/testbed/ {augment_log_root}/"
            )
        except Exception as e:
            pass

        logger.info(f"进程{process_id}: 完成处理 {instance_id} 第{attempt_idx}次尝试")

        return {
            "original_index": item.get("original_index", 0),
            "attempt_index": attempt_idx,
            "result": aug_result,
            "success": True
        }

    except Exception as e:
        error_msg = f"进程{process_id}: 处理 {instance_id or item.get('instance_id', 'unknown')} 第{attempt_idx}次尝试时出错: {e}"
        logger.error(error_msg)
        return {
            "original_index": item.get("original_index", 0),
            "attempt_index": attempt_idx,
            "result": {
                "success": False,
                "msg": str(e)
            }
        }
    finally:
        # 清理临时目录
        try:
            docker.shutdown()
        except Exception as e:
            logger.warning(f"进程{process_id}: 清理Docker容器时出错: {e}")


def run_augment_parallel(data: List[Dict[str, Any]], root: str, patch_root: str,
                         top_k: int, model_list: list, num_processes: int = None,
                         save_interval: int = 5) -> None:
    """并行执行augment任务

    Args:
        data: 评估数据列表
        root: 日志根目录
        patch_root: patch文件根目录
        top_k: 选择的top_k个patch
        majority_vote: 每个数据项的执行次数
        num_processes: 并行进程数，默认为CPU核心数
        save_interval: 每完成多少个任务后保存一次，默认为5
    """
    if num_processes is None:
        num_processes = multiprocessing.cpu_count()

    # 构建待处理任务列表
    pending_tasks = []
    for i, item in enumerate(data):
        if "augment_result" not in item:
            item["augment_result"] = [{"success": False, **x} for x in model_list]

        for attempt_idx in range(len(model_list)):
            if "success" in item["augment_result"][attempt_idx] and item["augment_result"][attempt_idx]["success"]:
                continue

            item_copy = copy.deepcopy(item)
            item_copy["original_index"] = i
            pending_tasks.append((item_copy, attempt_idx))

    if not pending_tasks:
        logger.info("所有数据已处理完成")
        return

    total_pending = len(pending_tasks)
    logger.info(f"开始异步处理，共{total_pending}个任务，使用{num_processes}个进程，每{save_interval}个任务保存一次")

    # 使用进程池并行处理
    with ProcessPoolExecutor(max_workers=num_processes) as executor:
        # 提交所有任务
        future_to_task = {
            executor.submit(_process_single_augment_task, item, idx, root, patch_root, attempt_idx, top_k, model_list[attempt_idx]): (item, attempt_idx) for idx, (item, attempt_idx) in enumerate(pending_tasks)
        }

        # 收集结果
        completed = 0
        last_save_count = 0

        for future in as_completed(future_to_task):
            try:
                result = future.result()
                original_index = result["original_index"]
                attempt_index = result["attempt_index"]
                for key, value in result["result"].items():
                    data[original_index]["augment_result"][attempt_index][key] = value

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
                item, attempt_idx = future_to_task[future]
                logger.error(
                    f"任务执行失败 - 实例ID: {item.get('instance_id', 'unknown')}, 尝试: {attempt_idx}, 错误: {e}")
                # 记录失败的任务信息
                original_index = item.get("original_index", 0)
                data[original_index]["augment_result"][attempt_idx]["success"] = False
                data[original_index]["augment_result"][attempt_idx]["msg"] = f"任务执行失败: {str(e)}"

    # 最终保存确保数据完整
    with open(os.path.join(root, "data.json"), "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logger.info("异步处理完成，结果已保存")


def is_finished(items, model_list):
    total_count = len(data) * len(model_list)
    count = 0

    for i, item in enumerate(items):
        if "augment_result" in item:
            for aug_result in item["augment_result"]:
                if "success" in aug_result and aug_result["success"]:
                    count += 1
        else:
            item["augment_result"] = [{"success": False, **model_config} for model_config in model_list]

    print(f"已经完成{count}条数据，剩余{total_count - count}条数据")
    return total_count - count > 0


def sortedby_scalar(items, score_path=None):
    if score_path and os.path.exists(score_path):
        with open(score_path, "r", encoding="utf-8") as f:
            score_config = json.load(f)
        # 把得分给他加进来
        for item in items:
            if "test_case_result" in item:
                for x in item["test_case_result"]:
                    instance = score_config[item["instance_id"]]
                    print(instance)
                    scalar = instance.get(x["file_name"].replace(".json", ""), 0)
                    print(scalar)
                    x["scalar"] = scalar
    else:
        for item in items:
            if "test_case_result" in item:
                for x in item["test_case_result"]:
                    x["scalar"] = 1.0

    for item in items:
        if "deibase_result" in item:
            item["deibase_result"] = sorted(item["deibase_result"], key=deibase_lambda, reverse=True)
        elif "test_case_result" in item:
            item["test_case_result"] = sorted(item["test_case_result"], key=test_case_lambda, reverse=True)
        else:
            raise RuntimeError(f"没有识别到任何的策略 - deibase/test_case_result")
    return items


def parse_args():
    parser = argparse.ArgumentParser(description='运行增强异步评估')

    # API配置参数
    parser.add_argument('--api-key', type=str, default=os.getenv('API-KEY', ''),
                        help='API密钥，默认从环境变量API-KEY读取')
    parser.add_argument('--base-url', type=str, default=os.getenv('BASE-URL', ''),
                        help='基础URL，默认从环境变量BASE-URL读取')
    parser.add_argument('--model', type=str, default=os.getenv('MODEL', 'Kimi-K2-Instruct'),
                        help='模型名称，默认从环境变量MODEL读取')
    parser.add_argument('--temperature', type=float, default="0",
                        help='温度参数，默认从环境变量TEMPERATURE读取')
    parser.add_argument('--docker-name', type=str, default=os.getenv('DOCKER-NAME', 'augment_runner'),
                        help='Docker容器名称，默认从环境变量DOCKER-NAME读取')

    # 路径配置参数
    parser.add_argument('--root', type=str, default=os.path.join(os.getcwd(), "augment_async_output"),
                        help='日志根目录，默认为当前目录下的augment_async_output')
    parser.add_argument('--score-path', type=str, help='score目录地址')
    parser.add_argument('--data-path', type=str, required=True,
                        help='输入数据文件路径')
    parser.add_argument('--patch-root', type=str, required=True,
                        help='patch文件根目录')
    parser.add_argument('--data-file', type=str, default="data.json",
                        help='数据文件名，默认为data.json')

    # 算法配置参数
    parser.add_argument('--top-k', type=int, default=3,
                        help='选择的top_k个patch，默认为3')
    parser.add_argument('--model-config', type=str, required=True,
                        help='模型配置文件路径，JSON格式，包含模型列表配置')

    # 进程配置参数
    parser.add_argument('--num-processes', type=int, default=multiprocessing.cpu_count(),
                        help='并行进程数，默认为CPU核心数')
    parser.add_argument('--save-interval', type=int, default=5,
                        help='每完成多少个任务后保存一次，默认为5')

    # 过滤参数
    parser.add_argument('--instance-id', type=str,
                        help='只处理指定instance_id的数据')

    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()

    # 设置环境变量
    os.environ["API-KEY"] = args.api_key
    os.environ["BASE-URL"] = args.base_url
    os.environ["MODEL"] = args.model
    os.environ["TEMPERATURE"] = str(args.temperature)
    os.environ["DOCKER-NAME"] = args.docker_name

    # 加载模型配置文件
    try:
        with open(args.model_config, 'r', encoding='utf-8') as f:
            model_list = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"模型配置文件错误或不存在: {e}")
        exit(1)

    # 加载并排序数据
    with open(args.data_path, "r", encoding='utf-8') as f:
        data = json.load(f)

    data = sortedby_scalar(data, args.score_path)

    # 创建目录
    os.makedirs(args.root, exist_ok=True)
    os.makedirs(os.path.join(args.root, "chat_history"), exist_ok=True)

    # 获取patch文件列表
    files = os.listdir(args.patch_root)
    files = [file for file in files if file.endswith(".jsonl") or file.endswith(".json")]
    files = [file for file in files if not file.startswith(".")]
    print(f"找到patch文件: {files}")

    # 加载或创建数据文件
    data_file_path = os.path.join(args.root, args.data_file)
    if os.path.exists(data_file_path):
        with open(data_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        with open(data_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"TOP K: {args.top_k}, MAJORITY VOTE: {len(model_list)}")

    # 过滤数据（如果指定了instance_id）
    # if args.instance_id:
    #     data = [item for item in data if item["instance_id"] == args.instance_id]
    #     logger.info(f"过滤后数据量: {len(data)}")

    # 使用并行模式运行
    retry_count = 0
    while is_finished(data, model_list) and retry_count < 10:
        run_augment_parallel(data=data, root=args.root, patch_root=args.patch_root,
                             top_k=args.top_k, model_list=model_list,
                             num_processes=args.num_processes, save_interval=args.save_interval)
        retry_count += 1