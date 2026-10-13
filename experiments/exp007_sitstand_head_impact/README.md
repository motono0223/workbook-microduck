# exp007: SitStand + 頭部の床衝撃ペナルティ（exp006 ベース）

## 目的
exp002 の方策は座るたびに頭部前面（jaw_soft）を床について支え、接触力は 11〜71 N に達した（32 体中 31 体）。
実機では頭部・サーボを傷めるおそれがあるため、頭部が床から受ける衝撃を罰して「頭をぶつけずに座る」方策を得る。

## 変更点（exp006 との差分）
- 接触センサー `head_ground_contact`: 頭部ボディ（neck, neck_pitch, yaw_roll_motion, jaw_soft）↔ terrain の合力
  - 公式 `HEAD_BODY_NAMES` の `bearing_roll` は右股関節リンク（公式コメントで誤記と明記）なので除外
- 報酬 `head_impact` = `body_impact_cost(threshold=15 N)`（公式 VelStand と同じ関数・同じ閾値）: 15 N 超の分 × **-0.02 / N**
  （公式 VelStand は -0.01。15 N 未満 = 静かに頭を添える程度は無料）
- 重みは 750 iter まで 25%、以降 100%（座る動作の発見を妨げないための段階導入。公式 VelStand と同じ考え方）
- それ以外は exp006 と同一（頭部指令ゼロ指令 30%, 最初から 3000 iter, seed 42）。`train_sitstand.py` が起動時に設定

## 評価
- `common/head_contact_probe.py`（立つ 2 秒 → 座る 4 秒 × 10, 32 体）で頭部接触の頻度・力を exp002 / exp006 と比較
- `common/eval_sitstand.py` のチェックポイント別評価（静かな条件 / 最終段の外乱）で座る・立つが悪化していないか確認

## 実行（リポジトリ直下）
```bash
docker compose -f docker/compose.yaml run -d --name microduck-rl-exp007 rl bash experiments/exp007_sitstand_head_impact/run.sh
```

## 結果
（実行中）
