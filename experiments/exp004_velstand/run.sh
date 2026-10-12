#!/usr/bin/env bash
# exp004_velstand: Mjlab-VelStand-Flat-MicroDuck を exp001 の歩行から warm start し、
# exp003 の起き上がりモデルを stand expert として蒸留（公式 VelStand のレシピ）。既定 3000 iter。
#
#   WALK_CKPT  : warm start 元 兼 walk anchor（既定: exp001 の model_2999.pt）
#   STAND_CKPT : stand expert（既定: exp003 の最新 run の最大 iteration の model_N.pt）
set -euo pipefail
EXP_DIR="$(cd "$(dirname "$0")" && pwd)"
RL_DIR="$EXP_DIR/../../submodules/microduck_rl"

WALK_CKPT="$(realpath "${WALK_CKPT:-$EXP_DIR/../exp001_baseline_velocity_flat/outputs/2026-10-10_08-15-27_exp001/model_2999.pt}")"
if [ -z "${STAND_CKPT:-}" ]; then
  RUN="$(ls -d "$EXP_DIR"/../exp003_standup/outputs/*_exp003 2>/dev/null | sort | tail -1)"
  # ファイル名の番号で数値ソート（パスに "_" を含むので sort -t_ は使えない。sort -V は名前部分だけを比較）
  STAND_CKPT="$(ls "$RUN"/model_*.pt 2>/dev/null | sort -V | tail -1)"
fi
[ -f "${STAND_CKPT:-}" ] || { echo "[exp004] STAND_CKPT が見つかりません（exp003 を先に学習）" >&2; exit 1; }
STAND_CKPT="$(realpath "$STAND_CKPT")"
echo "[exp004] walk : $WALK_CKPT"
echo "[exp004] stand: $STAND_CKPT"

# mjlab のローカル resume は logs/rsl_rl/<experiment_name>/<run>/<ckpt> から読むので、歩行の重みをそこに置く
WS_DIR="$RL_DIR/logs/rsl_rl/velstand/warmstart_walk"
mkdir -p "$WS_DIR"
cp "$WALK_CKPT" "$WS_DIR/$(basename "$WALK_CKPT")"

# MICRODUCK_WARM_START=1: 重み・正規化・optimizer は引き継ぎ、iteration とカリキュラムの step を 0 に戻す
export MICRODUCK_WARM_START=1
export STAND_EXPERT_CKPT="$STAND_CKPT" WALK_ANCHOR_CKPT="$WALK_CKPT"
TRAIN_CMD="uv run python $EXP_DIR/train_velstand.py" \
bash "$EXP_DIR/../common/train.sh" "$EXP_DIR" Mjlab-VelStand-Flat-MicroDuck "${RUN_NAME:-exp004}" \
  --agent.resume True --agent.load-run warmstart_walk --agent.load-checkpoint "$(basename "$WALK_CKPT")" \
  --agent.max-iterations "${MAX_ITERS:-3000}" --agent.logger tensorboard "$@"
