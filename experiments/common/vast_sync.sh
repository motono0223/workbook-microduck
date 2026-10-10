#!/usr/bin/env bash
# ローカル <-> vast.ai インスタンスの転送（rsync over ssh。差分のみ転送）
#
# 使い方:
#   export VAST_SSH="ssh -p <PORT> root@<HOST>"     # vast.ai の "Connect" に表示される ssh コマンド
#   bash experiments/common/vast_sync.sh push       # リポジトリ一式を送る
#   bash experiments/common/vast_sync.sh pull exp001_baseline_velocity_flat   # 結果を取ってくる
set -euo pipefail

: "${VAST_SSH:?VAST_SSH を設定してください（例: ssh -p 12345 root@1.2.3.4）}"
REMOTE_DIR="${REMOTE_DIR:-/workspace/workbook-microduck}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# "ssh -p PORT user@host" を rsync 用の -e 部分と宛先に分解
read -r -a parts <<<"$VAST_SSH"
DEST="${parts[-1]}"
SSH_CMD="${parts[*]:0:${#parts[@]}-1}"

case "${1:-}" in
  push)
    $VAST_SSH "mkdir -p $REMOTE_DIR"
    rsync -az --info=progress2 -e "$SSH_CMD" \
      --exclude '.venv/' --exclude '__pycache__/' --exclude 'outputs/' \
      --exclude 'submodules/microduck_rl/logs/' \
      "$REPO_ROOT/" "$DEST:$REMOTE_DIR/"
    ;;
  pull)
    EXP="${2:?実験ディレクトリ名を指定してください}"
    mkdir -p "$REPO_ROOT/experiments/$EXP/outputs"
    rsync -az --info=progress2 -e "$SSH_CMD" \
      "$DEST:$REMOTE_DIR/experiments/$EXP/outputs/" "$REPO_ROOT/experiments/$EXP/outputs/"
    ;;
  *)
    echo "usage: $0 push | pull <expNNN_...>" >&2; exit 1 ;;
esac
