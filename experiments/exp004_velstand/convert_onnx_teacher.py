"""公式 HF Hub の方策 ONNX（例: alpha_stand.onnx）を rsl_rl チェックポイント形式（.pt）に変換する。

exp003 / exp005 で自前の StandUp が倒れた状態からの起き上がりを発見できなかったため（4 シード全敗）、
VelStand の stand expert には公式の alpha_stand.onnx（pollen-robotics/microduck-policies, Apache-2.0）を使う。
distill.py は教師を ``load_state_dict(actor_state_dict, strict=True)`` で学生と同じ構造の actor に読み込むので、
ONNX の重みをその辞書形式に詰め直す。

ONNX の構造（export.py が観測正規化を焼き込んだもの）:
  Sub(obs_normalizer._mean) → Div(std + eps) → Gemm(mlp.0) → Elu → Gemm(mlp.2) → Elu → Gemm(mlp.4) → Elu → Gemm(mlp.6)
rsl_rl の EmpiricalNormalization は (x - mean) / (std + eps), eps = 1e-2 なので _std = Div 定数 - eps。

チェックポイントの外枠（critic / optimizer / infos）は同じ観測構成の既存チェックポイントから借りる
（distill も評価スクリプトも actor しか使わない）。変換後、ONNX と PyTorch の出力が一致することを確認する。

使い方（microduck_rl ディレクトリで）:
  uv run python ../../experiments/exp004_velstand/convert_onnx_teacher.py \
      --onnx ../../experiments/exp004_velstand/teachers/alpha_stand.onnx \
      --template <同じタスク系の既存 model_N.pt> --out ../../experiments/exp004_velstand/teachers/alpha_stand.pt
"""

from __future__ import annotations

import argparse

import numpy as np
import onnx
import onnxruntime as ort
import torch
from onnx import numpy_helper

EPS = 1e-2  # rsl_rl EmpiricalNormalization の既定 eps


def main() -> None:
  p = argparse.ArgumentParser()
  p.add_argument("--onnx", required=True)
  p.add_argument("--template", required=True, help="外枠を借りる既存チェックポイント（actor の形が同じもの）")
  p.add_argument("--out", required=True)
  p.add_argument("--iter", type=int, default=9750, help="ログ表示用の iteration（公式 stand expert は 69u48n8l@9750）")
  args = p.parse_args()

  model = onnx.load(args.onnx)
  init = {t.name: torch.from_numpy(numpy_helper.to_array(t).copy()) for t in model.graph.initializer}
  # Div ノードの第 2 入力 = std + eps
  div = next(n for n in model.graph.node if n.op_type == "Div")
  std_plus_eps = init[div.input[1]]
  mean = init["obs_normalizer._mean"]

  ck = torch.load(args.template, map_location="cpu", weights_only=False)
  actor = dict(ck["actor_state_dict"])
  for k in [k for k in actor if k.startswith("mlp.")]:
    if init[k].shape != actor[k].shape:
      raise ValueError(f"shape mismatch {k}: onnx {tuple(init[k].shape)} vs template {tuple(actor[k].shape)}")
    actor[k] = init[k].clone()
  std = std_plus_eps - EPS
  if (std <= 0).any():
    raise ValueError("std <= 0 after removing eps: Div 定数の解釈が違う可能性")
  actor["obs_normalizer._mean"] = mean.clone()
  actor["obs_normalizer._std"] = std.clone()
  actor["obs_normalizer._var"] = std.clone() ** 2
  actor["obs_normalizer.count"] = torch.tensor(10**9)  # 凍結教師なので更新されないが、大きくしておく
  # 決定的に使われる教師なので行動ノイズは使わない。学習済み方策らしい小さめの値を入れておく
  actor["distribution.std_param"] = torch.full_like(actor["distribution.std_param"], 0.2)

  out = {**ck, "actor_state_dict": actor, "iter": args.iter,
         "converted_from": args.onnx, "converted_note": "official ONNX weights; critic/optimizer/infos borrowed from template"}
  torch.save(out, args.out)

  # 検証: ONNX と同じ式を PyTorch で計算して比較
  sess = ort.InferenceSession(args.onnx, providers=["CPUExecutionProvider"])
  rng = np.random.default_rng(0)
  x = (rng.standard_normal((64, mean.shape[1])) * 2.0).astype(np.float32)
  name = sess.get_inputs()[0].name  # 入力はバッチ 1 固定
  y_onnx = np.concatenate([sess.run(None, {name: x[i:i + 1]})[0] for i in range(len(x))])
  h = (torch.from_numpy(x) - actor["obs_normalizer._mean"]) / (actor["obs_normalizer._std"] + EPS)
  for i in (0, 2, 4, 6):
    h = h @ actor[f"mlp.{i}.weight"].T + actor[f"mlp.{i}.bias"]
    if i != 6:
      h = torch.nn.functional.elu(h)
  err = float(np.abs(h.numpy() - y_onnx).max())
  print(f"[convert] wrote {args.out}  max|torch - onnx| = {err:.2e}")
  if err > 1e-4:
    raise SystemExit("[convert] output mismatch")


if __name__ == "__main__":
  main()
