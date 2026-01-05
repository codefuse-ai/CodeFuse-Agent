# Entropy-Guided Stepwise Scaling (EGSS)
![](./images/egss_overview.png)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## 🚀 Quick Start

### Run Dynamic Stepwise Search
TODO

### Run Test Consolidation Augmentation

Test Consolidation Augmentation is a multi-stage process that includes test case extraction and application, followed by enhancement processing. We provide two main execution scripts to automate this process.

#### 1. Basic Configuration

Before starting, configure the following environment variables and paths:

```bash
# Important Path
root="/your/project/root"
deibase_root="$root/deibase_output"
augment_root="$root/augment_output"  
traj_root="$root/traj"
patch_root="$root/patches"
test_consolidate_root="$root/test_consolidate_output"
score_path="$root/scores.json"

# data_path
data_path="path/to/swe-bench/test-00000-of-00001.parquet"

# API setting
api_key="your_api_key_here"
base_url="your_base_url_here" 
model="Kimi-K2-Instruct-0905"

# voting model config
voting_model_config="configs/moe_augment_model_config.json"
```

#### 2. Execution Scripts

##### Option 1: Deibase Augmentation Scheme (`run_deibase_augment.sh`)

Suitable for scenarios requiring Deibase processing and augmentation:

```bash
cd /path/to/egss
bash shell_cmd/run_deibase_augment.sh
```

**Core Parameter Description:**
- **Deibase Stage** (`run_deibase.py`):
  - `--api-key`: API key (required)
  - `--base-url`: API base URL (required) 
  - `--model`: Model to use, default `Kimi-K2-Instruct-0905`
  - `--docker-name`: Docker container name, default `glm_deibase_tts_8`
  - `--temperature`: Temperature parameter, default `0`
  - `--data-path`: Input data path (required)
  - `--root`: Output root directory (required)
  - `--patch-root`: Patch files root directory (required)
  - `--num-processes`: Number of processes, default CPU cores
  - `--save-interval`: Save interval, default `2`

- **Augmentation Stage** (`run_augment_async.py`):
  - `--docker-name`: Docker container name, default `glm_tts_8_moe_augment_runner`
  - `--data-path`: Input data path, typically Deibase output
  - `--root`: Augmentation output root directory (required)
  - `--patch-root`: Patch files root directory (required)
  - `--top-k`: Top-K selection, default `4`
  - `--model-config`: Model configuration file path (required)
  - `--num-processes`: Number of processes, default CPU cores

##### Option 2: Test Consolidation Augmentation Scheme (`run_test_consolidate.sh`)

Suitable for complete test case extraction, application, and augmentation workflow:

```bash
cd /path/to/egss
bash shell_cmd/run_test_consolidate.sh
```

**Three-Stage Process Description:**

1. **Test Case Extraction Stage** (`run_extract_test_case.py`):
   - `--api-key`, `--base-url`, `--model`: API configuration (required)
   - `--docker_name`: Docker container name, default `k2_tts_8_test_case_generator`
   - `--data-path`: Input data path
   - `--traj-root`: Trajectory files root directory (required)
   - `--root`: Test cases output root directory (required)
   - `--window-size`: Window size, default `2`
   - `--use-existing-data`: Use existing data flag
   - `--num-processes`: Number of processes, default CPU cores

2. **Test Case Application Stage** (`run_deibase_apply_test_case.py`):
   - `--api-key`, `--base-url`, `--model`: API configuration (required)
   - `--docker_name`: Docker container name, default `k2_tts_8_test_case_generator`
   - `--root`: Test case application output root directory (required)
   - `--patch-root`: Patch files root directory (required)
   - `--num-processes`: Number of processes, default CPU cores

3. **Augmentation Stage** (`run_augment_async.py`):
   - Same as Option 1's augmentation stage, but input data comes from test case application results
   - `--score-path`: Score file path for result evaluation

#### 3. Model Configuration File

The augmentation stage requires model combination configuration. Example configuration file `configs/moe_augment_model_config.json`:

```json
[
    {
        "model": "Kimi-K2-Instruct-0905",
        "prompt": "judge_trae_selector_prompt", 
        "temperature": 0.0
    },
    {
        "model": "Kimi-K2-Instruct-0905",
        "prompt": "judge_preference_prompt",
        "temperature": 0.0
    },
    {
        "model": "GLM-4.6",
        "prompt": "judge_trae_selector_prompt",
        "temperature": 1.0
    }
]
```

**Configuration Description:**
- `model`: Specific model name to use
- `prompt`: Prompt template, optional values include `judge_trae_selector_prompt`, `judge_preference_prompt`
- `temperature`: Model temperature parameter, controls generation randomness

#### 4. Execution Monitoring

Recommended to use `nohup` for background execution and save logs:

```bash
# Deibase augmentation scheme
nohup bash shell_cmd/run_deibase_augment.sh > ./deibase_augment.log 2>&1 &

# Test consolidation augmentation scheme  
nohup bash shell_cmd/run_test_consolidate.sh > ./test_consolidate.log 2>&1 &
```

#### 5. Output Structure

After execution completes, the following structure will be generated in the configured root directory:

```
project_root/
├── deibase_output/          # Deibase processing results
├── augment_output/          # Augmentation processing results
├── test_consolidate_output/ # Test consolidation results
├── traj/                    # Trajectory files
├── patches/                 # Patch files
└── scores.json             # Scoring results
```

