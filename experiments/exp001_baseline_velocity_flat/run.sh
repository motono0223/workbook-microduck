#!/usr/bin/env bash
# exp001: 公式 Velocity-Flat 歩行タスクを無改変で学習
set -euo pipefail

EXP_DIR="$(cd "$(dirname "$0")" && pwd)"
RL_DIR="$EXP_DIR/../../submodules/microduck_rl"
NUM_ENVS="${NUM_ENVS:-4096}"
RUN_NAME="${RUN_NAME:-exp001}"

mkdir -p "$EXP_DIR/outputs"
cd "$RL_DIR"
uv run train Mjlab-Velocity-Flat-MicroDuck \
  --env.scene.num-envs "$NUM_ENVS" \
  --agent.run-name "$RUN_NAME" \
  "$@" 2>&1 | tee "$EXP_DIR/outputs/train.log"

# mjlab は logs/ 以下に run を書き出すので、この実験の run を outputs/ に集約
find logs -maxdepth 3 -type d -name "*_${RUN_NAME}" -exec cp -r {} "$EXP_DIR/outputs/" \;

# 学習曲線の PNG / CSV を outputs/plots/ に書き出す
for d in "$EXP_DIR"/outputs/*_"${RUN_NAME}"; do
  uv run python "$EXP_DIR/../common/plot_training.py" "$d" --out "$EXP_DIR/outputs/plots" || true
done
