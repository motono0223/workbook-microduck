#!/usr/bin/env bash
# 学習を実行し、生成物を <exp_dir>/outputs/<日時>_<run名>/ に集約する共通スクリプト。
#   model_*.pt, *.onnx, events.*, params/, train.log, plots/
#
# 使い方: bash common/train.sh <exp_dir> <task_id> <run_name> [train の追加引数...]
#   環境変数: NUM_ENVS（既定 4096）, TRAIN_CMD（既定 "uv run train"。独自ランチャーを使う場合に差し替え）
set -euo pipefail

EXP_DIR="$(cd "$1" && pwd)"; TASK="$2"; RUN_NAME="$3"; shift 3
COMMON_DIR="$(cd "$(dirname "$0")" && pwd)"
RL_DIR="$COMMON_DIR/../../submodules/microduck_rl"
NUM_ENVS="${NUM_ENVS:-4096}"
TRAIN_CMD="${TRAIN_CMD:-uv run train}"

mkdir -p "$EXP_DIR/outputs"
# run ディレクトリ名は mjlab が学習開始時に日時から決めるため、ログは一時ファイルに書いて後で移す
TMP_LOG="$(mktemp "$EXP_DIR/outputs/train.XXXXXX.log")"
START_MARK="$(mktemp)"

cd "$RL_DIR"
$TRAIN_CMD "$TASK" \
  --env.scene.num-envs "$NUM_ENVS" \
  --agent.run-name "$RUN_NAME" \
  "$@" 2>&1 | tee "$TMP_LOG"

# 今回の学習で作られた run ディレクトリ（開始後に作成された *_RUN_NAME のうち最新）
SRC="$(find logs/rsl_rl -mindepth 2 -maxdepth 2 -type d -name "*_${RUN_NAME}" -newer "$START_MARK" \
       -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)"
rm -f "$START_MARK"
if [ -z "$SRC" ]; then
  echo "[train.sh] run ディレクトリが見つかりません。ログは $TMP_LOG に残しています" >&2
  exit 1
fi
RUN_DIR="$EXP_DIR/outputs/$(basename "$SRC")"
cp -r "$SRC" "$RUN_DIR"
mv "$TMP_LOG" "$RUN_DIR/train.log"

uv run python "$COMMON_DIR/plot_training.py" "$RUN_DIR" || true
echo "[train.sh] 出力: $RUN_DIR"
