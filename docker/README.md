# Docker 環境

mjlab (MuJoCo Warp) + PyTorch による Microduck RL 学習用のコンテナ。
依存はイメージに焼き込み、リポジトリはマウントして使う（実験コードの変更はすぐ反映される）。

## ビルド・実行（リポジトリ直下）

```bash
docker compose -f docker/compose.yaml build
# 対話シェル
docker compose -f docker/compose.yaml run --rm rl bash
# 実験を実行
docker compose -f docker/compose.yaml run --rm rl bash experiments/exp001_baseline_velocity_flat/run.sh
```

wandb を使う場合は `WANDB_API_KEY` を環境変数で渡す（オフラインなら `WANDB_MODE=offline`）。

## vast.ai での使い方

vast.ai のインスタンス自体が docker コンテナなので、次のどちらかで使う:

1. **イメージを使う**: このイメージを Docker Hub / GHCR に push し、vast.ai のテンプレートで
   そのイメージを指定する。インスタンス上で本リポジトリを `/workspace` に clone して実行。
2. **イメージを使わない**: CUDA 入りの標準イメージで起動し、`experiments/common/vast_setup.sh` を実行。

## ローカルサーバーでの注意

GPU は他コンペのコンテナと共用。ローカルではビルドと CPU での動作確認までにとどめ、
GPU を使う学習は vast.ai で行う。
