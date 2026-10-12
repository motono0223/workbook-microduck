#!/usr/bin/env bash
# exp005: StandUp をシードを変えて 1000 iter ずつ学習し、うつ伏せ・仰向けからの起き上がりを発見できたかを判定する。
#   SEEDS     : 試すシード（既定 "1 2 3"）
#   SCREEN_IT : 判定までの iteration（既定 1000）
# 各 run の判定結果は outputs/<run>/eval/standup_screen.json に保存。
set -euo pipefail
EXP_DIR="$(cd "$(dirname "$0")" && pwd)"
RL_DIR="$EXP_DIR/../../submodules/microduck_rl"
TASK=Mjlab-StandUp-Flat-MicroDuck
SCREEN_IT="${SCREEN_IT:-1000}"

for SEED in ${SEEDS:-1 2 3}; do
  RUN_NAME="exp005_s${SEED}"
  bash "$EXP_DIR/../common/train.sh" "$EXP_DIR" "$TASK" "$RUN_NAME" \
    --agent.seed "$SEED" --agent.max-iterations "$SCREEN_IT" --agent.logger tensorboard
  RUN_DIR="$(ls -d "$EXP_DIR"/outputs/*_"$RUN_NAME" | sort | tail -1)"
  CKPT="$(ls "$RUN_DIR"/model_*.pt | sort -V | tail -1)"
  mkdir -p "$RUN_DIR/eval"
  (cd "$RL_DIR" && uv run python "$EXP_DIR/../common/eval_standup.py" --task "$TASK" --checkpoint "$CKPT" \
     --num-envs 2048 --curriculum-iter 2500 --train-cfg --json "$RUN_DIR/eval/standup_screen.json") \
     | grep eval_standup || true
done
