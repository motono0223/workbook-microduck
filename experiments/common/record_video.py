"""学習済みチェックポイントで歩行動画（mp4）をヘッドレスで書き出す。

mjlab の `play --video` はビューアの起動が前提で DISPLAY の無い環境では動かないため、
play.py の環境・方策ロード部分だけを抜き出して EGL オフスクリーン描画で録画する。

使い方（microduck_rl ディレクトリで）:
  uv run python ../../experiments/common/record_video.py \
      --task Mjlab-Velocity-Flat-MicroDuck --checkpoint path/to/model_N.pt \
      --out walk.mp4 --steps 500
"""

from __future__ import annotations

import argparse
import os
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("MUJOCO_GL", "egl")

import imageio.v2 as imageio
import torch

from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.tasks.registry import load_env_cfg, load_rl_cfg, load_runner_cls
from mjlab.utils.torch import configure_torch_backends


def main() -> None:
  p = argparse.ArgumentParser()
  p.add_argument("--task", default="Mjlab-Velocity-Flat-MicroDuck")
  p.add_argument("--checkpoint", required=True)
  p.add_argument("--out", required=True)
  p.add_argument("--steps", type=int, default=500, help="制御ステップ数（50Hz）")
  p.add_argument("--width", type=int, default=640)
  p.add_argument("--height", type=int, default=480)
  p.add_argument("--distance", type=float, default=0.9, help="カメラ距離[m]（公式既定 3.0 は 25cm の機体には遠い）")
  p.add_argument("--elevation", type=float, default=-15.0)
  p.add_argument("--azimuth", type=float, default=120.0)
  args = p.parse_args()

  configure_torch_backends()
  device = "cuda:0" if torch.cuda.is_available() else "cpu"

  env_cfg = load_env_cfg(args.task, play=True)
  agent_cfg = load_rl_cfg(args.task)
  env_cfg.scene.num_envs = 1
  env_cfg.viewer.width = args.width
  env_cfg.viewer.height = args.height
  env_cfg.viewer.distance = args.distance
  env_cfg.viewer.elevation = args.elevation
  env_cfg.viewer.azimuth = args.azimuth

  env = ManagerBasedRlEnv(cfg=env_cfg, device=device, render_mode="rgb_array")
  fps = round(1.0 / env.step_dt)
  env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

  runner_cls = load_runner_cls(args.task) or MjlabOnPolicyRunner
  runner = runner_cls(env, asdict(agent_cfg), device=device)
  runner.load(args.checkpoint, load_cfg={"actor": True}, strict=True, map_location=device)
  policy = runner.get_inference_policy(device=device)

  out = Path(args.out)
  out.parent.mkdir(parents=True, exist_ok=True)
  obs = env.get_observations()
  with imageio.get_writer(out, fps=fps, codec="libx264", quality=8) as writer:
    for _ in range(args.steps):
      with torch.inference_mode():
        obs, _, _, _ = env.step(policy(obs))
      writer.append_data(env.unwrapped.render())
  env.close()
  print(f"[record_video] wrote {out} ({args.steps} steps @ {fps} fps)")


if __name__ == "__main__":
  main()
