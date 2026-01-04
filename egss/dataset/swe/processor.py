import os
import json
import regex as re

from dataset.processor import Preprocessor

def extract_repo(url: str) -> str | None:
    """
    从 code.alipay.com 的 URL 中提取 owner/repo。
    若不符合规范则返回 None。
    """
    pattern = re.compile(
        r'^https://code\.alipay\.com/([^/]+)/([^/]+)(?:/.*)?$',
        re.IGNORECASE
    )
    m = pattern.match(url.strip())
    return f"{m.group(1)}/{m.group(2)}" if m else None

def extract_pytest_stats(text: str):
    """
    从 pytest 输出的原始字符串中提取 passed 和 failed 的数量。
    兼容“只有 passed”、“只有 failed”以及“passed + failed”三种情况。

    参数
    ----
    text : str
        pytest 的原始输出字符串，可能包含 ANSI 转义码。

    返回
    ----
    tuple(int, int)
        (passed, failed)
    """
    # 去掉 ANSI 转义码
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    text = ansi_escape.sub('', text)

    # 匹配形如 "12 passed" 或 "1 passed, 2 failed" 的摘要行
    # 兼容 pytest 6/7 的输出格式
    pattern = re.compile(
        r'=?[\s\w]*?(\d+)\s+passed|=?[\s\w]*?(\d+)\s+failed',
        flags=re.IGNORECASE
    )

    passed = 0
    failed = 0

    # 逐行扫描，找到所有匹配
    for line in text.splitlines():
        # passed
        m = re.search(r'(\d+)\s+passed\b', line, re.IGNORECASE)
        if m:
            passed = int(m.group(1))
        # failed
        m = re.search(r'(\d+)\s+failed\b', line, re.IGNORECASE)
        if m:
            failed = int(m.group(1))

    return passed, failed



class SWE_Processor(Preprocessor):
    @staticmethod
    def process_swe_bench(path, **kwargs):
        lines = Preprocessor.load_data(path, folder_pattern='*log*')
        items = []

        for i, line in enumerate(lines):
            repo_name = line["repo"]
            instance_id = line["instance_id"]
            base_commit = line["base_commit"]
            patch = line["patch"]
            test_patch = line["test_patch"]
            rubric = ""
            query = line["problem_statement"]
            items.append({"repo": repo_name, "instance_id": instance_id, "base_commit": base_commit, "query": query, "patch": patch, "test_patch": test_patch, "rubric": rubric})
        return items

    @staticmethod
    def process_ant_bench(path, **kwargs):
        lines = Preprocessor.load_data(path, folder_pattern='*log*')
        items = []
        for i, line in enumerate(lines):
            commit = line["commit/pr"]
            repo = extract_repo(commit)
            parent_commit = line["parent commit"]

            instance_id = f"{repo}_{i}"
            instance_id = instance_id.replace("/", "__")
            patch = ""
            query = line["需求描述"]
            rubric = line["得分点"]
            score = line["复杂度"]
            items.append({"repo": repo, "instance_id": instance_id, "parent_commit": parent_commit, "query": query, "patch": patch, "rubric": rubric, "data_type": "ant", "score": score})
        return items

    @staticmethod
    def process_swe_bench_recall(path, chat_log_root=None, **kwargs):
        lines = Preprocessor.load_data(path, file_format='json', folder_pattern='*log*')
        items = []
        for i, line in enumerate(lines):
            if "result" in line and line["result"] and line["result"]["success"]:
                item = {
                    "repo": line["repo"],
                    "instance_id": line["instance_id"],
                    "query": line["query"]
                }
                if "chat_history" in line["result"]:
                    item["trajectory"] = line["result"]["chat_history"]["contents"]
                else:
                    files = os.listdir(chat_log_root)
                    files_list = True

                    # 如果 files 里的元素都没有后缀，则把它们当成目录
                    need_walk = any(not os.path.splitext(f)[1] and f not in {"logs", "step"} for f in files)

                    if need_walk:
                        for f in files:
                            if line["instance_id"] in f:
                                target_dir = f
                                break
                        else:
                            raise FileNotFoundError("找不到包含该 instance_id 的目录")
                    else:
                        # 本身就是文件列表，直接取第一个匹配的文件
                        target_dir = next(f for f in files if line["instance_id"] in f)

                    # 读取对应轨迹
                    with open(os.path.join(chat_log_root, target_dir, "chat_history.json"), "r") as f:
                        item["trajectory"] = json.load(f)
                items.append(item)
            else:
                continue

        return items

    @staticmethod
    def process_ant_repo(path, root=""):
        if not root:
            root = os.path.dirname(path)
        lines = Preprocessor.load_data(path, file_format='csv', folder_pattern='*log*')
        items = []
        for i, line in enumerate(lines):
            ai_commit = line.get("ai commit", None)
            if not ai_commit:
                continue
            # ai_commit: https://code.alipay.com/lzy-test/linkc-fork/commit/6422dcffd4b84dc2d400aaa9627a7c35df0520d6
            # 抽取commit_id和repo,比如上面这个case要提取出：6422dcffd4b84dc2d400aaa9627a7c35df0520d6和linkc-fork
            parts = ai_commit.split('/')
            current_commit_id = parts[-1]  # 最后一个部分是commit_id
            repo = parts[-3]  # 倒数第三个部分是repo名称
            item = {
                "current_commit_id": current_commit_id,
                "commit_id": line["parent commit"],
                "rubric": line["得分点"],
                "query": line["需求描述"],
                "path": os.path.join(root, repo)
            }
            items.append(item)
        return items