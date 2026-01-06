# nohup sh script/run_deibase_augment.sh > ./deibase_glm_tts_8.log 2>&1 &

root=""
deibase_root="$root/x"
augment_root="$root/x"
traj_root="$root/traj"
patch_root="$root/patches"

voting_model_config="xx/moe_augment_model_config.json"
data_path="path/to/swe-bench/test-00000-of-00001.parquet"
docker_config_path="xx/docker_config_swebench_verified.json"

api_key=""
base_url=""
model=""

python run_deibase.py \
  --api-key $api_key \
  --base-url $base_url \
  --model $model \
  --docker-name "glm_deibase_tts_8" \
  --temperature 0 \
  --data-path $data_path \
  --root $deibase_root \
  --patch-root $patch_root \
  --docker-config-path $docker_config_path \
  --num-processes 8 \
  --save-interval 2

python run_augment_async.py \
  --docker-name "glm_tts_8_moe_augment_runner" \
  --temperature 0 \
  --data-path "$deibase_root/data.json" \
  --root $augment_root \
  --patch-root $patch_root \
  --top-k 4 \
  --model-config $voting_model_config \
  --docker-config-path $docker_config_path \
  --num-processes 8 \
  --save-interval 2