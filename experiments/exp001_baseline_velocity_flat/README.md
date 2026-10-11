# exp001: Velocity-Flat ベースライン再現

## 目的
公式の歩行タスク `Mjlab-Velocity-Flat-MicroDuck` を無改変で学習し、
以降の実験の比較基準（学習曲線・所要時間・歩容）を得る。

## 変更点
なし（公式設定そのまま）。

## 実行
ローカル Docker（リポジトリ直下で）:
```bash
RUN_NAME=exp001 NUM_ENVS=4096 docker compose -f docker/compose.yaml run -d --name microduck-rl-exp001 rl \
  bash experiments/exp001_baseline_velocity_flat/run.sh --agent.max-iterations 3000 --agent.logger tensorboard
# 動画（学習後）
docker compose -f docker/compose.yaml run --rm rl \
  bash experiments/exp001_baseline_velocity_flat/make_video.sh experiments/exp001_baseline_velocity_flat/outputs/<run>/model_2999.pt
```
vast.ai: `common/vast_setup.sh` の後に `run.sh` を同じ引数で実行。

公式 README の目安: 4096 envs で 1〜2 時間で使える歩容。公式既定の max_iterations は 50,000 だが、
まずは 3000 iteration（RTX 3090 で約 2.2 s/iter → 約 1.8 h）で打ち切る。

## 生成物
学習 1 回分の出力はすべて run ディレクトリ `outputs/<日時>_<RUN_NAME>/` にまとまる（再学習しても上書きされない）。
- `model_N.pt` … チェックポイント（250 iter ごと, PyTorch 重み）
- `<run名>.onnx` … 実機デプロイ用 ONNX（学習時に自動書き出し, 観測正規化込み）
- `events.out.tfevents.*` … tensorboard ログ / `params/` … 学習時の env・agent 設定
- `train.log` … 標準出力
- `plots/*.png`, `plots/scalars.csv` … 学習曲線（`common/plot_training.py`, run.sh 終了時に自動生成）
- `videos/*.mp4` … `make_video.sh` で書き出した歩行動画（既定でチェックポイントと同じ run の videos/ に出る）
- `summary.md` … モデル・報酬設計の解説と結果の可視化

## 記録する項目
- GPU 種別 / num_envs / 学習時間 / iteration 数
- wandb run パス
- 主要指標: 平均報酬、episode 長、速度追従誤差、各 penalty 項が ≤ 0 か
- play での目視所見

## 結果（2026-10-10, ローカル RTX 3090 / Docker）
- 4096 envs × 3000 iter、所要 1h57m（約 1.9〜2.2 s/iter）、VRAM 約 5.7 GB
- run: `outputs/2026-10-10_08-15-27_exp001/`（最終: `model_2999.pt`, `2026-10-10_08-15-27_exp001.onnx`）
- 動画: `outputs/2026-10-10_08-15-27_exp001/videos/model_2999.mp4`（20 秒, ランダム速度・頭部姿勢コマンド, 転倒なし）
- 詳細レポート: `outputs/2026-10-10_08-15-27_exp001/summary.md`（モデル・報酬設計の解説、プロット・動画付き）
- 途中経過の動画: `outputs/2026-10-10_08-15-27_exp001/videos/model_{0,250,500}.mp4`（サムネイル `strip_model_*.png`）

| iter | Mean reward | Ep 長 | vel_xy 誤差 | yaw 誤差 | 頭部姿勢カリキュラム |
|---|---|---|---|---|---|
| 0 | -0.01 | 24 | - | - | 0.07 |
| 250 | 102.6 | 934 | 0.52 | 3.13 | 0.07 |
| 1000 | 114.0 | 935 | 0.45 | 1.68 | 0.49 |
| 2000 | 111.8 | 926 | 0.42 | 1.11 | 1.40 (上限) |
| 2999 | 114.6 | 960 | 0.42 | 1.10 | 1.40 |

最終時の報酬内訳: penalty 項はすべて ≤ 0（AGENTS.md の健全性チェック OK）。
最大の負項は `action_rate_l2` (-1.04)、次いで `head_pose_bias` (-0.26)。

## 考察
- 250 iter（約 9 分）で転倒しない歩行を獲得。以降はカリキュラム（頭部姿勢範囲・静止 env 比率）が広がりつつ
  yaw 追従が改善。2000 iter 前後でカリキュラム上限に到達し、報酬・誤差とも頭打ち。
- 学習曲線（`outputs/2026-10-10_08-15-27_exp001/plots/`）: カリキュラムが段階的に難しくなる 500/1000/1500/2000 iter で
  報酬が一時的に落ち、すぐ回復する鋸歯状のパターン。`head_pose_bias` ペナルティも同じ段で深くなる。
  方策の std は 1.0 → 0.19 まで収束、`action_rate_l2` は重みが -0.1 → -1.0 に上がるため負に大きくなる（悪化ではない）。
- `dof_pos_limits` ペナルティが 2000 iter 以降じわじわ悪化（頭部姿勢範囲が上限になった影響と思われる, 絶対値は小）。
- スループットが 1500 iter 付近で一時半減（25k steps/s）。他コンテナの GPU 負荷と重なった可能性。
- 直進速度誤差 0.42 はまだ大きめ。公式既定 50,000 iter まで回すとどこまで下がるかは未検証。
- 次の候補: 長時間学習（例 10,000 iter）、Backlash 版タスク（sim2real 向け）、速度追従の改善。
