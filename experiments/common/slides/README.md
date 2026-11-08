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
