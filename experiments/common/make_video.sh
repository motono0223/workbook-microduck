#!/usr/bin/env bash
# 学習済みチェックポイントで動画(mp4)を書き出す（ヘッドレス EGL。ローカル WSL2 では compose.wsl.yaml を重ねて GPU 描画）
# 使い方: bash common/make_video.sh <task_id> <checkpoint.pt> [steps(50Hz, 既定500=10秒)] [out.mp4] [record_video.py の追加引数...]
#   out 省略時: チェックポイントと同じ run ディレクトリの videos/<ckpt名>.mp4
set -euo pipefail
COMMON_DIR="$(cd "$(dirname "$0")" && pwd)"
RL_DIR="$COMMON_DIR/../../submodules/microduck_rl"
TASK="$1"
CKPT="$(realpath "$2")"
STEPS="${3:-500}"
OUT="$(realpath -m "${4:-$(dirname "$CKPT")/videos/$(basename "$CKPT" .pt).mp4}")"

cd "$RL_DIR"
uv run python "$COMMON_DIR/record_video.py" \
  --task "$TASK" --checkpoint "$CKPT" --steps "$STEPS" --out "$OUT" "${@:5}"
