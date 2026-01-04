from pathlib import Path
from typing import List
import regex as re
from utils.cmd_utils import run_cmd


def set_folder_permissions(root: str,
                           mode: str,
                           whitelist: List[str] = None,
                           follow_symlinks: bool = False):
    """
    根据模式批量设置文件夹权限。

    :param root:        目标目录
    :param mode:        'readonly' | 'write'
    :param whitelist:   在 readonly 模式下保持可读写的文件路径（支持绝对或相对路径）
    :param follow_symlinks: 是否跟随符号链接
    """
    root_path = Path(root).expanduser().resolve()

    if not root_path.is_dir():
        raise ValueError(f"{root_path} 不是有效目录")

    if mode not in ('readonly', 'write'):
        raise ValueError("mode 只能是 'readonly' 或 'write'")

    # 把白名单统一转成绝对路径，便于比较
    whitelist_abs = []
    if whitelist:
        whitelist_abs = [Path(w).expanduser().resolve() for w in whitelist]

    # 使用find命令获取所有文件和目录
    find_cmd = f"find '{root_path}' -type f"
    if not follow_symlinks:
        find_cmd += " -type f ! -type l"

    try:
        files_output = run_cmd(find_cmd, verbose=False)
        files = [f.strip() for f in files_output.split('\n') if f.strip()]
    except:
        files = []

    # 处理文件权限
    for file_path in files:
        f = Path(file_path)

        # 跳过符号链接检查
        if not follow_symlinks and f.is_symlink():
            continue

        if mode == 'readonly':
            # 在白名单里的文件用 644，否则 444
            perm = "644" if whitelist_abs and f in whitelist_abs else "444"
        else:  # write
            perm = "666"

        run_cmd(f"chmod {perm} '{file_path}'", verbose=False)

    # 处理目录权限
    find_dirs_cmd = f"find '{root_path}' -type d"
    if not follow_symlinks:
        find_dirs_cmd += " ! -type l"

    try:
        dirs_output = run_cmd(find_dirs_cmd, verbose=False)
        dirs = [d.strip() for d in dirs_output.split('\n') if d.strip()]
    except:
        dirs = []

    for dir_path in dirs:
        d = Path(dir_path)

        # 跳过符号链接检查
        if not follow_symlinks and d.is_symlink():
            continue

        if mode == 'readonly':
            # 目录设为只读：755（读/执行，防止无法遍历）
            perm = "755"
        else:  # write
            # 目录设为所有人可读写执行
            perm = "777"

        run_cmd(f"chmod {perm} '{dir_path}'", verbose=False)


def filter_diff(patch, black_list=None):
    if not black_list:
        black_list = [".buildinfo", ".doctree", ".log", ".txt", ".json", ".png", ".jpg", ".md", ".pdf", ".svg", ".rst", ".pickle", ".js", ".css", ".html", ".inv"]
    block_re = re.compile(r'^diff --git\s+.*$', re.MULTILINE)
    chunks = block_re.split(patch)
    headers = block_re.findall(patch)
    # 3. 过滤：去掉 .png / .txt 或 路径中带 test 的块
    out = []
    for h, c in zip(headers, chunks[1:]):
        fname = h.split()[-1]          # b/xxx 部分
        flag = False
        for item in black_list:
            if fname.endswith(item):
                flag = True
                break
        if flag:
            continue
        out.append(h + c)
    # 4. 输出
    filtered = ''.join(out)
    return filtered