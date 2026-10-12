# exp003: StandUp（起き上がり）

## 目的
公式タスク `Mjlab-StandUp-Flat-MicroDuck` を無改変・最初から学習し、うつ伏せ・仰向け・座位から立ち上がる方策を得る。
この方策は exp004（VelStand）で **stand expert（倒れた状態の動きを教える先生）** として使う。

## タスクの概要（cfg docstring より）
- 初期姿勢: 座位、うつ伏せ（face-down）、仰向け（face-up）など。`ground_state_mix` カリキュラムで
  2500 iter までに難しい初期姿勢の割合を増やす
- 目標: 立位の keyframe（胴体高さ約 0.12 m）。経路は指定せず方策に発見させる
- 立った後は胴体姿勢指令（高さ・ロール・ピッチ）に追従。2500 iter から有効化
- やさしさは |鉛直加速度| の罰則で表現

## 設定
- 変更点: なし（公式設定）
- 4096 envs × 5000 iter（カリキュラム最終段は 4000 iter）。公式の stand expert は 9750 iter 時点のもの
  （VelStand では倒れたフレームの教師として 100%/100%/95%（うつ伏せ/仰向け/横向き）の起き上がり率と記載）

## 実行（リポジトリ直下）
```bash
docker compose -f docker/compose.yaml run -d --name microduck-rl-exp003 rl bash experiments/exp003_standup/run.sh
docker compose -f docker/compose.yaml -f docker/compose.wsl.yaml run --rm rl \
  bash experiments/exp003_standup/make_video.sh experiments/exp003_standup/outputs/<run>/model_4999.pt 1000
```

## 生成物
`outputs/<日時>_exp003/`（exp002 と同じ構成）。

## 結果（2026-10-12, ローカル RTX 3090）— 倒れた状態からの起き上がりは未獲得
- 4096 envs × 5000 iter、所要 3h19m。詳細は `outputs/2026-10-12_03-30-00_exp003/summary.md`
- 起き上がり成功率（2048 体, 最終段の初期姿勢）: 座位など 99%、**うつ伏せ・仰向け・横向き 0%**（全チェックポイント）
- 学習曲線は公式 cfg に記録された「失敗 run」の特徴（1500/2500 iter で立位指標が落ちて戻らない）と一致
