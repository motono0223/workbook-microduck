# exp004: VelStand（歩行 + 転倒時の保護 + 起き上がり を 1 つの方策で）

## 目的
公式の VelStand レシピを自前のモデルで再現する:
- **warm start**: exp001 の歩行方策（`model_2999.pt`）の重み・観測正規化・optimizer を引き継いで開始
- **蒸留**: exp003 の起き上がり方策を **stand expert** とし、倒れた状態（傾き > 35°）のフレームで模倣させる。
  立っているフレーム（傾き < 25°）は exp001 の歩行に **anchor**（固定）して、歩行が壊れないようにする
  （公式 `tasks/distill.py`: PPO + 転倒時ゲート付き behavior cloning）

## なぜ warm start + 蒸留か（公式 docs/velstand_policy.md, distill.py より）
最初から学習・歩行の warm start だけ、のどちらでも「倒れたまま一度も起き上がらない」。歩行方策は行動ノイズが小さく
（std ≈ 0.2）、寝た状態から偶然起き上がる動きが出ないため報酬が発生しない。起き上がりを知っている expert から教える。

## 公式からの変更点
- 教師チェックポイントの取得元: 公式は pollen-robotics の wandb（441tzs6d@3750, 69u48n8l@9750）→
  ローカルの exp001 / exp003 の .pt に差し替え（`train_velstand.py` が実行時に `bc_cfg` を書き換える。サブモジュールは無改変）
- iteration: 公式上限 6000 に対し、まず 3000（必要なら resume で延長）

## 実行（リポジトリ直下, exp003 完了後）
```bash
docker compose -f docker/compose.yaml run -d --name microduck-rl-exp004 rl bash experiments/exp004_velstand/run.sh
# 教師を明示する場合: -e WALK_CKPT=... -e STAND_CKPT=...（既定は exp001 model_2999 / exp003 最新 run の最大 iter）
```
`run.sh` は歩行の重みを `submodules/microduck_rl/logs/rsl_rl/velstand/warmstart_walk/` に置いて resume し、
`MICRODUCK_WARM_START=1` で iteration とカリキュラムを 0 から始める（公式の注意: これを忘れると
カリキュラムが 1 iter 目から最終段に飛ぶ）。

## 生成物
`outputs/<日時>_exp004/`（exp002 と同じ構成）。

## 結果
（未実施）
