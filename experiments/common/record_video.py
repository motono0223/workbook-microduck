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
import mujoco
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
  p.add_argument("--curriculum-iter", type=int, default=None,
                 help="この iteration 時点のカリキュラム（初期姿勢・外乱・指令範囲）で録画。"
                      "省略時はチェックポイントに保存された段階（= 学習終了時）。0 = 最易段")
  p.add_argument("--train-cfg", action="store_true", help="play ではなく学習用の env 設定を使う")
  p.add_argument("--sit-schedule", default=None,
                 help="SitStand 用: 姿勢指令の時間割 例 'stand:2,sit:5,stand:5'（秒）。指定時はランダム再抽選を止めて上書き")
  p.add_argument("--head-still", action="store_true", help="頭部指令をゼロに固定（再抽選を止める）")
  p.add_argument("--episode-s", type=float, default=None, help="エピソード長を上書き（録画途中の時間切れリセットを避ける）")
  p.add_argument("--log-pose-every", type=int, default=0,
                 help="N ステップごとに全個体の姿勢統計（傾き>60° の数, 胴体高さ, 頭部高さ）を表示（評価スクリプトとの照合用）")
  args = p.parse_args()

  configure_torch_backends()
  device = "cuda:0" if torch.cuda.is_available() else "cpu"

  env_cfg = load_env_cfg(args.task, play=not args.train_cfg)
  agent_cfg = load_rl_cfg(args.task)
  env_cfg.scene.num_envs = args.num_envs
  if args.episode_s is not None:
    env_cfg.episode_length_s = args.episode_s
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
    # mujoco.Renderer の既定 max_geom=10000 は約 140 体分（1 体 ≈ 70 geom）。超える分は描画されないので作り直す
    off = env._offline_renderer
    need = 80 * args.num_envs + 1000
    if need > off.renderer.scene.maxgeom:
      off.close()
      off._renderer = mujoco.Renderer(model=off._model, height=args.height, width=args.width, max_geom=need)
  fps = round(1.0 / env.step_dt / args.render_every)
  env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

  runner_cls = load_runner_cls(args.task) or MjlabOnPolicyRunner
  runner = runner_cls(env, asdict(agent_cfg), device=device)
  runner.load(args.checkpoint, load_cfg={"actor": True}, strict=True, map_location=device)
  policy = runner.get_inference_policy(device=device)

  out = Path(args.out)
  out.parent.mkdir(parents=True, exist_ok=True)
  # runner.load() はチェックポイントの common_step_counter を書き戻すが、ラッパー生成時の初回 reset は
  # それより前（カウンタ 0 = 最易段）に済んでいる。そのままだと最初のエピソードだけ最易段になるので、
  # 段階を確定させてから全 env を reset し、動画全体を 1 つの段階にそろえる。
  if args.curriculum_iter is not None:
    env.unwrapped.common_step_counter = args.curriculum_iter * 24
  env.reset()
  schedule = []
  if args.sit_schedule:
    for item in args.sit_schedule.split(","):
      name, sec = item.split(":")
      schedule += [1.0 if name == "sit" else 0.0] * int(round(float(sec) / env.unwrapped.step_dt))

  def override_commands(step: int) -> None:
    # 再抽選を止める（time_left を大きく）うえで指令を書き込む
    cm = env.unwrapped.command_manager
    if schedule:
      tw = cm.get_term("twist")
      tw.time_left[:] = 1e9
      tw.vel_command_b[:] = 0.0
      tw.vel_command_b[:, 0] = schedule[min(step, len(schedule) - 1)]
    if args.head_still:
      hp = cm.get_term("head_pose")
      hp.time_left[:] = 1e9
      hp._command[:] = 0.0

  if schedule or args.head_still:
    override_commands(0)
  obs = env.get_observations()
  t0 = time.time()
  with imageio.get_writer(out, fps=fps, codec="libx264", quality=8) as writer:
    for i in range(args.steps):
      with torch.inference_mode():
        obs, _, _, _ = env.step(policy(obs))
        if schedule or args.head_still:
          override_commands(i + 1)
          obs = env.get_observations()  # 上書きした指令を次の行動の観測に反映
      if i % args.render_every == 0 and not os.environ.get("RV_SKIP_RENDER"):
        writer.append_data(env.unwrapped.render())
      if args.log_pose_every and i % args.log_pose_every == 0:
        r = env.unwrapped.scene["robot"]
        tilt = torch.rad2deg(torch.acos((-r.data.projected_gravity_b[:, 2]).clamp(-1, 1)))
        z = r.data.root_link_pos_w[:, 2]
        cmd = env.unwrapped.command_manager.get_command("twist")[:, 0] if "twist" in env.unwrapped.command_manager.active_terms else None
        print(f"[pose] step={i} t={i * env.unwrapped.step_dt:.1f}s tilt>60:{int((tilt > 60).sum())} tilt>30:{int((tilt > 30).sum())}"
              f" z<0.05:{int((z < 0.05).sum())} z_med={float(z.median()):.3f} tilt_max={float(tilt.max()):.0f}"
              + (f" sit_cmd:{int((cmd > 0.5).sum())}" if cmd is not None else "") + f" / {z.numel()}")
  env.close()
  dt = time.time() - t0
  print(f"[record_video] wrote {out} ({args.steps} steps @ {fps} fps, {dt / args.steps * args.render_every:.2f} s/frame)")


if __name__ == "__main__":
  main()
