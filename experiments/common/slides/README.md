# 実験ごとの PowerPoint 資料の生成

各 `expNNN_*/slides/expNNN.pptx` を生成したスクリプト一式（聞き手: データサイエンティスト）。
1 exp = 1 デッキで、モデルの入出力・MuJoCo の実行条件・報酬関数・ハイパーパラメータ・学習曲線（ネイティブグラフ）・
評価結果・推論動画（mp4 埋め込み）を同じ構成で説明する。

- `extract.py <run_dir> <out.json> [tag ...]` … `params/*.yaml`・`train.log`・`plots/scalars.csv` から観測/行動次元、
  シミュレーション条件、報酬・終了条件・ランダム化・カリキュラム、PPO 設定、学習曲線（間引き）を JSON に抜き出す
- `content.js` … 各 exp の文章（要点・目的・変更点・結論）、使う動画・画像、報酬項/観測項/イベントの説明辞書
- `build.js <outDir> [expId ...]` … pptxgenjs でデッキを生成（評価値は各 run の `eval/*.json` をまとめた `data/evals.json` から読む）
- `videos.txt` … 動画と表紙フレームの時刻

生成時は `npm install pptxgenjs@3.12.0` した作業ディレクトリに `data/`（extract.py の出力と evals.json）と
`posters/`（videos.txt の時刻で切り出した PNG）を置き、`NODE_PATH=<node_modules> node build.js out` を実行する。
`build.js` 冒頭の apply_theme.js は pptx スキルのスクリプトを参照している。

## 付録: 報酬関数の解説（2026-11 追加）
各デッキの末尾に「報酬関数の読み方」と、報酬項ごとの解説スライド（1 枚 2 項目: 数式・記号・何を測る・なぜ必要・有効条件・関数の形のグラフ）を付けている。
- `reward_terms.json` … 4 タスクの run の params/env.yaml から作った「報酬名 → 実装関数・パラメータ・重み」
- `build_reward_explain.py` → `reward_explain.json` … 実装コード（mjlab / mjlab_microduck の mdp.py）と cfg のコメントから
  各項の数式・意図・グラフ用の点列（コードの式で計算）をまとめたもの。build.js がこれを読む
- 注意: VelStand では 6 項目（upright, pose, body_pose_tracking, action_rate_l2, joint_torque_rate_l2, air_time）が
  同名のまま別関数に差し替えられており、解説では Velocity 版の式を示し差分を「有効条件」に記載している
