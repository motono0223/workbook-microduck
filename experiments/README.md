# experiments

Microduck 制御ポリシーの学習試行。1 試行 = 1 ディレクトリ。

## ルール

- ディレクトリ名は `expNNN_<短い説明>`（例: `exp001_baseline_velocity_flat`）。番号は通し。
- `submodules/microduck_rl` は**直接編集しない**。変更が必要な場合は実験ディレクトリ内に置く:
  - `patch.diff` … 公式リポジトリへの差分（vast.ai 上でコピーに `git apply`）
  - もしくは独自タスク cfg / スクリプト
- 各実験に必ず置くもの:
  - `README.md` … 目的・仮説・変更点・実行コマンド・結果・考察
  - `run.sh` … そのまま実行できる学習スクリプト（中身は `common/train.sh` の呼び出し）
  - `make_video.sh` … 動画書き出し（`common/make_video.sh` の呼び出し）
- 学習 1 回分の出力（チェックポイント・ONNX・train.log・プロット・動画・summary.md）は
  run ディレクトリ `outputs/<日時>_<run名>/` にまとめ、git にもコミットする。
  実験をまたぐ比較図が必要になったら、run の外に比較用ディレクトリを別に作る
  （GitHub の 1 ファイル 100MB 制限に注意。超える場合は Git LFS か除外を検討）。

## 実行環境

- **ローカルサーバーでは GPU 学習をしない**（他コンペの docker / GPU ジョブと共用のため）。
  ローカルではコード編集・結果分析・軽い CPU チェックのみ。
- GPU 学習は基本 vast.ai。ただしユーザーの許可がある場合はローカル Docker（`docker/`）で実行する
  （4096 envs で VRAM 約 6 GB）。初期セットアップは `common/vast_setup.sh`。
- 起き上がり成功率は `common/eval_standup.py`（初期姿勢別）。
- 転倒率は `common/eval_falls.py`（N 体をヘッドレスで動かし傾きで判定、`--curriculum-iter` で外乱の段階を指定）。
- 学習曲線は `common/plot_training.py <run_dir>`（tensorboard ログ → PNG 5 枚 + CSV）。
- 動画は `common/record_video.py`（ヘッドレス EGL 録画、mjlab の `play --video` は DISPLAY 必須のため）。
  `--num-envs N` で多数個体を俯瞰。ローカル（WSL2）では `-f docker/compose.wsl.yaml` を重ねて GPU 描画する（約 100 倍速い）。
- ローカル <-> vast.ai の転送は `common/vast_sync.sh push` / `pull <exp名>`（rsync over ssh）。

## 実験一覧

| ID | 内容 | 状態 | 結果 |
|---|---|---|---|
| exp001 | 公式 Velocity-Flat 歩行タスクのベースライン再現 | 完了 | 3000 iter/1h57m で安定歩行。reward 114.6, vel_xy 誤差 0.42 |
| exp002 | SitStand（座る⇄立つ）を最初から学習 | 完了 | 3000 iter/2h07m。250 iter で座る/立つ獲得。最終外乱下で 20 秒に約 5% が座位で後ろに傾く |
| exp003 | StandUp（起き上がり）を最初から学習。exp004 の stand expert | 完了（失敗） | 5000 iter/3h19m。座位からは 99% 起立、うつ伏せ・仰向け・横向きからは 0%（公式記録の失敗パターンと同じ） |
| exp004 | VelStand：exp001 から warm start + exp003 を蒸留 | 保留 | exp003 が倒れた状態から起き上がれないため未実行 |
| exp005 | StandUp のシード探索（seed 1/2/3 × 1000 iter → 起き上がれた run を延長） | 実行中 | - |
