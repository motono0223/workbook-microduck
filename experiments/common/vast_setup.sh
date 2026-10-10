#!/usr/bin/env bash
# vast.ai インスタンスの初期セットアップ（CUDA 入りイメージ想定, x86_64）。
# 使い方: bash experiments/common/vast_setup.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RL_DIR="$REPO_ROOT/submodules/microduck_rl"

nvidia-smi

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# 初回は CUDA 系 wheel が大きいのでタイムアウトを延ばす
export UV_HTTP_TIMEOUT=600
cd "$RL_DIR"
uv sync

# 動作確認: タスク一覧が出ればOK
uv run list-envs | head -40

cat <<MSG
セットアップ完了。wandb を使う場合は: uv run wandb login
MSG
