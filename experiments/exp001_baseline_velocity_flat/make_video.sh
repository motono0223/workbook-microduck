#!/usr/bin/env bash
# 学習済みチェックポイントで歩行動画(mp4)を書き出す（ヘッドレス / EGL）
# 使い方: bash make_video.sh <checkpoint.pt> [steps(50Hz, 既定500=10秒)] [out.mp4]
set -euo pipefail
EXP_DIR="$(cd "$(dirname "$0")" && pwd)"
RL_DIR="$EXP_DIR/../../submodules/microduck_rl"
CKPT="$(realpath "$1")"
STEPS="${2:-500}"
OUT="$(realpath -m "${3:-$EXP_DIR/outputs/videos/$(basename "$CKPT" .pt).mp4}")"

cd "$RL_DIR"
uv run python "$EXP_DIR/../common/record_video.py" \
  --task Mjlab-Velocity-Flat-MicroDuck --checkpoint "$CKPT" --steps "$STEPS" --out "$OUT"
