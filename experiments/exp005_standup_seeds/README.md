# exp005: StandUp のシード探索（倒れた状態からの起き上がりの発見）

## 目的
exp003（seed 42）はうつ伏せ・仰向け・横向きからの起き上がりを発見できなかった（成功率 0%）。
公式 cfg によると起き上がりの発見はシード頼み（同等の報酬で 1 勝 3 敗）なので、シードを変えて再挑戦し、
発見できた run だけを延長して exp004（VelStand）の stand expert を得る。

## 方法
1. `run.sh`: seed 1, 2, 3 で各 1000 iter 学習（設定は exp003 と同じ公式設定、シードのみ変更）
2. 各 run の最終チェックポイントを `common/eval_standup.py` で評価（2048 体, 最終段の初期姿勢分布）→ `outputs/<run>/eval/standup_screen.json`
   - うつ伏せは学習開始時から 20%、仰向けは 600 iter から混ざるので、1000 iter 時点で発見の有無を判定できる見込み
3. `continue.sh <run名>`: 起き上がれた run を同じタスクのまま resume し 5000 iter まで延長（iteration・カリキュラムは続きから）

## 実行（リポジトリ直下）
```bash
docker compose -f docker/compose.yaml run -d --name microduck-rl-exp005 rl bash experiments/exp005_standup_seeds/run.sh
docker compose -f docker/compose.yaml run -d --name microduck-rl-exp005c rl bash experiments/exp005_standup_seeds/continue.sh <run名>
```

## 結果
（実行中）
