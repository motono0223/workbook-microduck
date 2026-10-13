#!/usr/bin/env bash
# exp006: SitStand + 頭部指令のゼロ指令バケット（既定 30%）。exp002 と同条件（最初から, 3000 iter, seed 42）で比較する。
set -euo pipefail
EXP_DIR="$(cd "$(dirname "$0")" && pwd)"
export HEAD_ZERO_PROB="${HEAD_ZERO_PROB:-0.3}"
TRAIN_CMD="uv run python $EXP_DIR/train_sitstand.py" \
bash "$EXP_DIR/../common/train.sh" "$EXP_DIR" Mjlab-SitStand-Flat-MicroDuck "${RUN_NAME:-exp006}" \
  --agent.max-iterations "${MAX_ITERS:-3000}" --agent.logger tensorboard "$@"
