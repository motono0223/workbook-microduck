#!/usr/bin/env bash
# exp005: 判定を通過した run を同じタスクのまま resume して延長する（iteration とカリキュラムは続きから）。
# 使い方: bash continue.sh <run 名 例: 2026-10-12_xx-xx-xx_exp005_s2> [追加 iteration 数, 既定 4000]
set -euo pipefail
EXP_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_RUN="$1"; ADD="${2:-4000}"
SRC="$EXP_DIR/outputs/$SRC_RUN"
CKPT="$(basename "$(ls "$SRC"/model_*.pt | sort -V | tail -1)")"
# mjlab のローカル resume は logs/rsl_rl/<experiment_name>/<run>/ から読む（train.sh はコピーなので元が残っている）
bash "$EXP_DIR/../common/train.sh" "$EXP_DIR" Mjlab-StandUp-Flat-MicroDuck "exp005_${SRC_RUN##*_exp005_}_cont" \
  --agent.resume True --agent.load-run "$SRC_RUN" --agent.load-checkpoint "$CKPT" \
  --agent.max-iterations "$ADD" --agent.logger tensorboard
