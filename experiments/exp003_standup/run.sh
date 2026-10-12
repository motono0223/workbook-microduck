#!/usr/bin/env bash
# exp003_standup: Mjlab-StandUp-Flat-MicroDuck を最初から学習（既定 5000 iter）
set -euo pipefail
EXP_DIR="$(cd "$(dirname "$0")" && pwd)"
bash "$EXP_DIR/../common/train.sh" "$EXP_DIR" Mjlab-StandUp-Flat-MicroDuck "${RUN_NAME:-exp003}" \
  --agent.max-iterations "${MAX_ITERS:-5000}" --agent.logger tensorboard "$@"
