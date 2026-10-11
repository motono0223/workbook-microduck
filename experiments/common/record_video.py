"""学習済みチェックポイントで歩行動画（mp4）をヘッドレスで書き出す。

mjlab の `play --video` はビューアの起動が前提で DISPLAY の無い環境では動かないため、
play.py の環境・方策ロード部分だけを抜き出して EGL オフスクリーン描画で録画する。

使い方（microduck_rl ディレクトリで）:
  uv run python ../../experiments/common/record_video.py \
      --task Mjlab-Velocity-Flat-MicroDuck --checkpoint path/to/model_N.pt \
      --out walk.mp4 --steps 500

  多数の個体をまとめて映す（固定カメラで群れを俯瞰）:
  uv run python ../../experiments/common/record_video.py ... --num-envs 36 --spacing 1.0
"""

from __future__ import annotations

import argparse
import os
import time
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("MUJOCO_GL", "egl")

import imageio.v2 as imageio
import numpy as np
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
  p.add_argument("--num-envs", type=int, default=1,
                 help="2 以上で多数個体モード: 全個体を描画し、固定カメラで群れの中心を映す")
  p.add_argument("--spacing", type=float, default=1.0,
                 help="多数個体モードでの個体間隔[m]（学習時は 2.0）")
  p.add_argument("--no-shadows", action="store_true",
                 help="影と床の反射を切る（CPU のソフトウェア描画では大幅に速くなる）")
  p.add_argument("--render-every", type=int, default=1,
                 help="N ステップに 1 回だけ描画（動画は 50/N fps、再生速度は実時間のまま）")
  args = p.parse_args()

  configure_torch_backends()
  device = "cuda:0" if torch.cuda.is_available() else "cpu"

  env_cfg = load_env_cfg(args.task, play=True)
  agent_cfg = load_rl_cfg(args.task)
  env_cfg.scene.num_envs = args.num_envs
  multi = args.num_envs > 1
  if multi:
    env_cfg.scene.env_spacing = args.spacing
    if env_cfg.scene.terrain is not None:
      env_cfg.scene.terrain.env_spacing = args.spacing
    env_cfg.viewer.max_extra_envs = args.num_envs - 1  # 全個体を描画
    env_cfg.viewer.origin_type = env_cfg.viewer.OriginType.WORLD  # 追従しない固定カメラ
  env_cfg.viewer.width = args.width
  env_cfg.viewer.height = args.height
  env_cfg.viewer.distance = args.distance
  env_cfg.viewer.elevation = args.elevation
  env_cfg.viewer.azimuth = args.azimuth
  if args.no_shadows:
    env_cfg.viewer.enable_shadows = False
    env_cfg.viewer.enable_reflections = False

  env = ManagerBasedRlEnv(cfg=env_cfg, device=device, render_mode="rgb_array")
  if multi:
    # 個体の配置（env_origins）は環境生成後にしか分からないので、ここでカメラ注視点を群れの中心に合わせる
    origins = env.scene.env_origins.cpu().numpy()
    cam = env._offline_renderer._cam
    cam.lookat[:] = origins.mean(axis=0) + np.array([0.0, 0.0, 0.1])
  fps = round(1.0 / env.step_dt / args.render_every)
  env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

  runner_cls = load_runner_cls(args.task) or MjlabOnPolicyRunner
  runner = runner_cls(env, asdict(agent_cfg), device=device)
  runner.load(args.checkpoint, load_cfg={"actor": True}, strict=True, map_location=device)
  policy = runner.get_inference_policy(device=device)

  out = Path(args.out)
  out.parent.mkdir(parents=True, exist_ok=True)
  obs = env.get_observations()
  t0 = time.time()
  with imageio.get_writer(out, fps=fps, codec="libx264", quality=8) as writer:
    for i in range(args.steps):
      with torch.inference_mode():
        obs, _, _, _ = env.step(policy(obs))
      if i % args.render_every == 0:
        writer.append_data(env.unwrapped.render())
  env.close()
  dt = time.time() - t0
  print(f"[record_video] wrote {out} ({args.steps} steps @ {fps} fps, {dt / args.steps * args.render_every:.2f} s/frame)")


if __name__ == "__main__":
  main()
