#!/usr/bin/env bash
# マウントされた microduck_rl を /opt/venv に editable で入れる（依存は焼き込み済みなので数秒）
set -e
RL_DIR=/workspace/submodules/microduck_rl
if [ -f "$RL_DIR/pyproject.toml" ]; then
  (cd "$RL_DIR" && uv sync --frozen --quiet)
fi
# コンテナは root で動くので、終了時に生成物の所有者をホストユーザーへ戻す
fix_owner() {
  if [ -n "${HOST_UID:-}" ]; then
    chown -R "$HOST_UID:${HOST_GID:-$HOST_UID}" /workspace/experiments "$RL_DIR/logs" 2>/dev/null || true
  fi
}
trap fix_owner EXIT
"$@"
