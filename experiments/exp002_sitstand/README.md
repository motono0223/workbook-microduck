# exp002: SitStand（座る ⇄ 立つ）

## 目的
公式タスク `Mjlab-SitStand-Flat-MicroDuck` を無改変・最初から学習し、指令で座る/立つを切り替える方策を得る。
SitStand → StandUp → VelStand の順で進める一連の実験の 1 本目（exp003, exp004 参照）。

## タスクの概要（公式 `docs/sitstand_policy.md`, cfg docstring より）
- 1 つの方策で「座る ⇄ 立つ」を指令で切り替える。姿勢フラグは速度指令の vx スロット（0 = 立つ, 1 = 座る）
- 座位・立位の両方で頭部姿勢指令に追従
- 動作は「ゆっくり・やさしく」（急な動きは罰則）

## 設定
- 変更点: なし（公式設定）
- 4096 envs × 3000 iter（カリキュラムは 2500 iter で最終段に到達）。公式の採用チェックポイントは
  ベース run の 1250 iter、追加学習後の 2250 iter
- 公式の既知の欠点: 座位で頭を急に動かすと後ろに倒れ、30° 傾いたまま首サーボが過負荷になる

## 実行（リポジトリ直下）
```bash
docker compose -f docker/compose.yaml run -d --name microduck-rl-exp002 rl bash experiments/exp002_sitstand/run.sh
# 動画（ローカル WSL2 は GPU 描画の上書きを重ねる）
docker compose -f docker/compose.yaml -f docker/compose.wsl.yaml run --rm rl \
  bash experiments/exp002_sitstand/make_video.sh experiments/exp002_sitstand/outputs/<run>/model_2999.pt 1000
```
`MAX_ITERS`, `NUM_ENVS`, `RUN_NAME` は環境変数で上書き可。

## 生成物
`outputs/<日時>_exp002/` に model_*.pt / ONNX / tensorboard / params / train.log / plots / videos / summary.md。

## 結果（2026-10-12, ローカル RTX 3090）
- 4096 envs × 3000 iter、所要 2h07m。詳細は `outputs/2026-10-12_01-19-41_exp002/summary.md`
- 指令どおりの姿勢になれた割合（1024 体, `common/eval_sitstand.py`）:

  | | 学習終了時の条件 座る / 立つ | 外乱なし 座る / 立つ |
  |---|---|---|
  | model_2250 | **93% / 89%** | 67% / 99% |
  | model_2999 | 92% / 79%（21% が座位で後ろに傾いて立てない） | 65% / 100% |
- 外乱なしでは「座れ」指令の約 1/3 で座らない（原因未調査）。当面の採用候補は model_2250
