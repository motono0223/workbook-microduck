# exp006: SitStand + 頭部指令のゼロ指令バケット

## 目的
exp002 の切り分け（summary 4.4）で、**頭部指令がほぼゼロだと「座れ」指令の約 1/3 を無視する**ことが分かった
（model_2250: 頭部指令が最小範囲だと座る 67%、最終範囲なら 91%）。学習後半は頭部指令が常に大きく振られるため、
頭を静止したまま座る経験が少ないと考えられる。実機で頭を動かさずに座らせる場面に直結する。

## 変更点（exp002 との差分は 1 つだけ）
- `commands.head_pose.zero_command_prob = 0.3`: 頭部指令の再サンプル時に 30% の確率で全ゼロにする
  （公式実装済みの機能で SitStand では 0。`train_sitstand.py` が起動時に設定。サブモジュールは無改変）
- それ以外は exp002 と同じ（最初から学習, 3000 iter, seed 42, 4096 envs）

## 評価
`common/eval_sitstand.py` で exp002 と同条件に加え、`--head-zero-prob 1.0`（頭を常に静止）でも比較する。

## 実行（リポジトリ直下）
```bash
docker compose -f docker/compose.yaml run -d --name microduck-rl-exp006 rl bash experiments/exp006_sitstand_zero_head/run.sh
```

## 結果
（実行中）
