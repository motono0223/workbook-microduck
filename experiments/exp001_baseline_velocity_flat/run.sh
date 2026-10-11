#!/usr/bin/env bash
# exp001: 公式 Velocity-Flat 歩行タスクを無改変で学習
# 1 回の学習の生成物はすべて outputs/<日時>_<RUN_NAME>/ にまとまる:
#   model_*.pt, *.onnx, events.*, params/, train.log, plots/
set -euo pipefail

EXP_DIR="$(cd "$(dirname "$0")" && pwd)"
RL_DIR="$EXP_DIR/../../submodules/microduck_rl"
NUM_ENVS="${NUM_ENVS:-4096}"
RUN_NAME="${RUN_NAME:-exp001}"

mkdir -p "$EXP_DIR/outputs"
# run ディレクトリ名は mjlab が学習開始時に日時から決めるため、ログは一時ファイルに書いて後で移す
TMP_LOG="$(mktemp "$EXP_DIR/outputs/train.XXXXXX.log")"

cd "$RL_DIR"
START_MARK="$(mktemp)"
uv run train Mjlab-Velocity-Flat-MicroDuck \
  --env.scene.num-envs "$NUM_ENVS" \
  --agent.run-name "$RUN_NAME" \
  "$@" 2>&1 | tee "$TMP_LOG"

# 今回の学習で作られた run ディレクトリ（開始後に作成された *_RUN_NAME のうち最新）
SRC="$(find logs/rsl_rl -mindepth 2 -maxdepth 2 -type d -name "*_${RUN_NAME}" -newer "$START_MARK" \
       -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)"
rm -f "$START_MARK"
if [ -z "$SRC" ]; then
  echo "[run.sh] run ディレクトリが見つかりません。ログは $TMP_LOG に残しています" >&2
  exit 1
fi
RUN_DIR="$EXP_DIR/outputs/$(basename "$SRC")"
cp -r "$SRC" "$RUN_DIR"
mv "$TMP_LOG" "$RUN_DIR/train.log"

# 学習曲線の PNG / CSV を <run>/plots/ に書き出す
uv run python "$EXP_DIR/../common/plot_training.py" "$RUN_DIR" || true
echo "[run.sh] 出力: $RUN_DIR"
