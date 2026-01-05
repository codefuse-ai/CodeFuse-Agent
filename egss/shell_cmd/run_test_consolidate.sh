# nohup sh script/run_test_consolidate.sh > ./tca_k2-tts-8-all.log 2>&1 &
root=""
test_consolidate_root="$root/x"
augment_root="$root/x"
traj_root="$root/traj"
patch_root="$root/patches"
score_path="$root/x.json"
data_path="path/to/swe-bench/test-00000-of-00001.parquet"
docker_config_path=""

api_key=""
base_url=""
model=""
voting_model_config="xx/moe_augment_model_config.json"

python run_extract_test_case.py \
  --api-key $api_key \
  --base-url $base_url \
  --model $model \
  --docker_name "k2_tts_8_test_case_generator" \
  --temperature 0 \
  --data-path $data_path \
  --traj-root  $traj_root\
  --root $test_consolidate_root \
  --docker-config-path $docker_config_path \
  --window-size 2 \
  --use-existing-data \
  --num-processes 8 \
  --save-interval 2

python run_deibase_apply_test_case.py \
  --api-key $api_key \
  --base-url $base_url \
  --model $model \
  --docker_name "k2_tts_8_test_case_generator" \
  --temperature 0 \
  --root $test_consolidate_root \
  --docker-config-path $docker_config_path \
  --patch-root $patch_root \
  --num-processes 8 \
  --save-interval 2


python run_augment_async.py \
  --docker-name "k2_tts_8_moe_augment_runner" \
  --temperature 0 \
  --data-path "$test_consolidate_root/data.json" \
  --root $augment_root \
  --patch-root $patch_root \
  --top-k 4 \
  --model-config $voting_model_config \
  --score-path $score_path \
  --docker-config-path $docker_config_path \
  --num-processes 8 \
  --save-interval 2