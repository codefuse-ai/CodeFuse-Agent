#!/usr/bin/env python3
import glob
import json
import os.path
from pathlib import Path

#采样数目
total = 8
#需要处理的文件路径
path = ""
pattern = os.path.join(path, "")
pattern_path = glob.glob(pattern)
out_path = ""
model_name = 'glm'
out_files = []
for i in range(1, total + 1):
    out_files.append(Path(os.path.join(out_path, f'patches_{i}.json')))
pred = {}
index = 0
sorted_pattern_path = sorted(pattern_path, key=lambda path: int(path.split('index_')[-1]))
print(sorted_pattern_path)
for pat in sorted_pattern_path[:total]:
    patches_list={}
    files = Path(pat).iterdir()
    ab = len(list(files))
    for d in Path(pat).iterdir():
        if not d.is_dir():
            continue
        a = str(d).split("/")[-1]
        model_files = [f for f in d.iterdir() if f.is_file() and 'model' in f.name]
        with open(model_files[0], encoding='latin-1') as f:
            try:
                patch = f.read()
            except Exception as e:
                print(e)
            if patch:
                patches_list[a]= {
                    'model_patch': patch,
                    'model_name_or_path': model_name
                }
            else:
                print("patch is None")
    try:
        with open(out_files[index], "w") as f:
            json.dump(patches_list, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(e)
    print(f"✓ 步骤{index}处理完成，结果已写入 {out_files[index]}")
    with open(out_files[index], "r") as f:
        data = json.load(f)
        print("生成文件的个数是",len(data))
    index+=1
print("✓ 全部处理完成")