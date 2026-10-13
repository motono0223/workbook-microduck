"""頭部が床に接触しているかを MuJoCo の衝突判定で数える（描画なし）。

各ステップ、各 env の qpos を CPU 側の MjData に写して mj_forward（衝突判定を含む）し、
「頭部サブツリー（neck_pitch 以下）のジオメトリ ↔ 床（ロボット以外のジオメトリ, mjlab では terrain ボディ）」の接触を探す。
接触力は mj_contactForce の法線成分。

  uv run python ../../experiments/common/head_contact_probe.py --task Mjlab-SitStand-Flat-MicroDuck \
      --checkpoint model_2000.pt --num-envs 64 --steps 1200 --curriculum-iter 0 --head-zero-prob 1.0
"""

from __future__ import annotations

import argparse
import json

import mujoco
import numpy as np
import torch

from evalutil import make_env_and_policy, warmup_until_auto_reset

HEAD_ROOT = "neck_pitch"


def head_geom_ids(model: mujoco.MjModel) -> set[int]:
  root = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, HEAD_ROOT)
  if root < 0:
    root = next(b for b in range(model.nbody) if model.body(b).name.endswith(HEAD_ROOT))
  bodies = set()
  for b in range(model.nbody):
    a = b
    while a > 0:
      if a == root:
        bodies.add(b)
        break
      a = model.body_parentid[a]
  return {g for g in range(model.ngeom) if model.geom_bodyid[g] in bodies}


def main() -> None:
  p = argparse.ArgumentParser()
  p.add_argument("--task", default="Mjlab-SitStand-Flat-MicroDuck")
  p.add_argument("--checkpoint", required=True)
  p.add_argument("--num-envs", type=int, default=64)
  p.add_argument("--steps", type=int, default=1200)
  p.add_argument("--curriculum-iter", type=int, default=0)
  p.add_argument("--head-zero-prob", type=float, default=None)
  p.add_argument("--sit-schedule", default=None, help="'stand:2,sit:4,...' で姿勢指令を固定（record_video と同じ）")
  p.add_argument("--log-contacts", action="store_true", help="env 0 の接触を時刻つきで表示")
  p.add_argument("--json", default=None)
  args = p.parse_args()

  def hook(cfg):
    if args.head_zero_prob is not None:
      cfg.commands["head_pose"].zero_command_prob = args.head_zero_prob
    if args.sit_schedule:
      cfg.episode_length_s = max(cfg.episode_length_s, args.steps * 0.02 + 10)

  _, base, env, policy, device = make_env_and_policy(
    args.task, args.checkpoint, args.num_envs, args.curriculum_iter, True, cfg_hook=hook)
  obs, _ = warmup_until_auto_reset(base, env, policy)

  schedule = []
  if args.sit_schedule:
    for item in args.sit_schedule.split(","):
      name, sec = item.split(":")
      schedule += [1.0 if name == "sit" else 0.0] * int(round(float(sec) / base.step_dt))
  tw = base.command_manager.get_term("twist")

  model = base.sim.mj_model
  data = mujoco.MjData(model)
  head = head_geom_ids(model)
  # 床（mjlab では 'terrain' という独立ボディ。ワールド本体 body 0 ではない）= ロボット以外のジオメトリ
  robot_bodies = {b for b in range(model.nbody) if model.body(b).name.startswith("robot/")}
  world_geoms = {g for g in range(model.ngeom) if model.geom_bodyid[g] not in robot_bodies}
  if not world_geoms:
    raise RuntimeError("床のジオメトリが見つからない")
  force = np.zeros(6)

  n = args.num_envs
  touch_steps = {"sit": 0, "stand": 0}
  steps_per = {"sit": 0, "stand": 0}
  env_touched = np.zeros(n, dtype=bool)
  max_force = 0.0
  first_touch_t = []
  for step in range(args.steps):
    if schedule:
      tw.time_left[:] = 1e9
      tw.vel_command_b[:] = 0.0
      tw.vel_command_b[:, 0] = schedule[min(step, len(schedule) - 1)]
      obs = env.get_observations()
    with torch.inference_mode():
      obs, _, _, _ = env.step(policy(obs))
    flag = (base.command_manager.get_command("twist")[:, 0] > 0.5).cpu().numpy()
    qpos = base.sim.data.qpos.cpu().numpy()
    qvel = base.sim.data.qvel.cpu().numpy()
    for i in range(n):
      data.qpos[:] = qpos[i]
      data.qvel[:] = qvel[i]
      mujoco.mj_forward(model, data)
      touched, f_max = False, 0.0
      for c in range(data.ncon):
        con = data.contact[c]
        g1, g2 = int(con.geom1), int(con.geom2)
        if (g1 in head and g2 in world_geoms) or (g2 in head and g1 in world_geoms):
          mujoco.mj_contactForce(model, data, c, force)
          touched, f_max = True, max(f_max, abs(force[0]))
      key = "sit" if flag[i] else "stand"
      steps_per[key] += 1
      if touched and args.log_contacts and not env_touched[i]:  # 各 env の最初の接触だけ表示
        names = sorted({model.body(model.geom_bodyid[int(con.geom1 if int(con.geom1) in head else con.geom2)]).name
                        for con in data.contact[:data.ncon]
                        if (int(con.geom1) in head) or (int(con.geom2) in head)})
        cmd_t = step * base.step_dt
        print(f"[contact] env={i} t={cmd_t:.2f}s cmd={'sit' if flag[i] else 'stand'} force={f_max:.1f}N bodies={names} "
              f"trunk_z={qpos[i][2]:.3f}")
      if touched:
        touch_steps[key] += 1
        if not env_touched[i]:
          first_touch_t.append(step * base.step_dt)
        env_touched[i] = True
        max_force = max(max_force, f_max)

  res = {
    "checkpoint": args.checkpoint, "num_envs": n, "steps": args.steps, "curriculum_iter": args.curriculum_iter,
    "head_zero_prob": args.head_zero_prob, "sit_schedule": args.sit_schedule, "head_geoms": len(head),
    "envs_with_head_floor_contact": int(env_touched.sum()),
    "head_contact_time_frac_while_sit_cmd": touch_steps["sit"] / max(steps_per["sit"], 1),
    "head_contact_time_frac_while_stand_cmd": touch_steps["stand"] / max(steps_per["stand"], 1),
    "max_head_contact_normal_force_N": max_force,
  }
  print("[head_contact] " + json.dumps(res, ensure_ascii=False))
  if args.json:
    with open(args.json, "w") as f:
      json.dump(res, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
  main()
