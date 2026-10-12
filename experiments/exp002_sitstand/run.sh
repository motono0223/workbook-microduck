#!/usr/bin/env bash
# exp002_sitstand: Mjlab-SitStand-Flat-MicroDuck を最初から学習（既定 3000 iter）
set -euo pipefail
EXP_DIR="$(cd "$(dirname "$0")" && pwd)"
bash "$EXP_DIR/../common/train.sh" "$EXP_DIR" Mjlab-SitStand-Flat-MicroDuck "${RUN_NAME:-exp002}" \
  --agent.max-iterations "${MAX_ITERS:-3000}" --agent.logger tensorboard "$@"
