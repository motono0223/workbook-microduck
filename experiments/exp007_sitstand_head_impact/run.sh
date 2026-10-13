#!/usr/bin/env bash
# exp007: exp006 + 頭部の床衝撃ペナルティ（15 N 超 × -0.02/N, 750 iter まで 25%）。最初から 3000 iter, seed 42。
set -euo pipefail
EXP_DIR="$(cd "$(dirname "$0")" && pwd)"
TRAIN_CMD="uv run python $EXP_DIR/train_sitstand.py" \
bash "$EXP_DIR/../common/train.sh" "$EXP_DIR" Mjlab-SitStand-Flat-MicroDuck "${RUN_NAME:-exp007}" \
  --agent.max-iterations "${MAX_ITERS:-3000}" --agent.logger tensorboard "$@"
