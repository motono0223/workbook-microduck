# Microduck RL 学習用イメージ（mjlab / MuJoCo Warp / PyTorch, x86_64 + NVIDIA GPU）
# CUDA ランタイムは torch / warp の wheel が同梱するため、ベースは軽量な base イメージで足りる。
FROM nvidia/cuda:12.9.1-base-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    UV_HTTP_TIMEOUT=600 \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    MUJOCO_GL=egl \
    PATH=/root/.local/bin:$PATH

# git: bam を git から取得 / EGL・GL: ヘッドレス描画（動画記録）用
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git tmux \
      libegl1 libgl1 libglib2.0-0 libosmesa6 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# 依存だけ先に入れてレイヤキャッシュを効かせる（プロジェクト本体は実行時にマウント）
WORKDIR /build
COPY submodules/microduck_rl/pyproject.toml submodules/microduck_rl/uv.lock ./
RUN uv python install 3.12 && uv sync --frozen --no-install-project

WORKDIR /workspace
ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
