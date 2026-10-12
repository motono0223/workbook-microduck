"""SitStand 方策が指令どおりの姿勢になれているかを多数個体でヘッドレス評価する（描画なし）。

全 env が一度自動リセットされた後（evalutil.warmup_until_auto_reset）から --steps 動かし、
指令（twist の vx = 姿勢フラグ: 1 = 座る, 0 = 立つ）が切り替わってから --settle-s 秒以上たったサンプルで姿勢を分類する:
  ok        : 指令姿勢に到達（座位: 胴体高さ 0.060±tol かつ 傾き<25° ／ 立位: 0.115±tol かつ 傾き<20°）、頭部は正常
  leaned    : 傾き 25〜60°（座位で後ろに傾いたまま等）
  lying     : 傾き > 60°
  head_down : 頭部の高さ < 0.07 m（頭を地面について支えている／突っ伏している。正常な座位で約 0.16 m）
  wrong     : 座れ指令なのに立位の高さ（> 0.10 m）のまま／立て指令なのに座位の高さ（< 0.08 m）のまま
（ok 以外は重複しうる）

使い方（microduck_rl ディレクトリで）:
  uv run python ../../experiments/common/eval_sitstand.py --checkpoint path/to/model_N.pt --curriculum-iter 3000 --train-cfg
"""

from __future__ import annotations

import argparse
import json

import torch

from evalutil import make_env_and_policy, warmup_until_auto_reset

SIT_Z, STAND_Z = 0.060, 0.115
HEAD_BODIES = ("yaw_roll_motion", "jaw_soft")  # 頭部（座位の基準姿勢で z ≈ 0.16〜0.18 m）
HEAD_DOWN_Z = 0.07


def main() -> None:
  p = argparse.ArgumentParser()
  p.add_argument("--task", default="Mjlab-SitStand-Flat-MicroDuck")
  p.add_argument("--checkpoint", required=True)
  p.add_argument("--num-envs", type=int, default=1024)
  p.add_argument("--steps", type=int, default=1200, help="測定する制御ステップ数（50Hz）。warm-up の 1 エピソードは別")
  p.add_argument("--curriculum-iter", type=int, default=0)
  p.add_argument("--train-cfg", action="store_true")
  p.add_argument("--spacing", type=float, default=None)
  p.add_argument("--settle-s", type=float, default=2.5, help="指令切替からこの秒数以上たったサンプルで判定")
  p.add_argument("--tol", type=float, default=0.015, help="高さの許容誤差 [m]")
  p.add_argument("--pin", action="append", default=[],
                 help="カリキュラム項目を固定: 項目名=first|last（複数可, 切り分け評価用）")
  p.add_argument("--log-every", type=int, default=0, help="N ステップごとに姿勢統計を表示")
  p.add_argument("--json", default=None)
  args = p.parse_args()

  _, base, env, policy, device = make_env_and_policy(
    args.task, args.checkpoint, args.num_envs, args.curriculum_iter, args.train_cfg, args.spacing,
    pins=args.pin)
  obs, _ = warmup_until_auto_reset(base, env, policy)
  robot = base.scene["robot"]
  head_ids, _ = robot.find_bodies(HEAD_BODIES)

  n = args.num_envs
  settle = int(round(args.settle_s / base.step_dt))
  since = torch.zeros(n, dtype=torch.long, device=device)
  prev_flag = base.command_manager.get_command("twist")[:, 0] > 0.5
  keys = ("samples", "ok", "leaned", "lying", "head_down", "wrong")
  stats = {c: dict.fromkeys(keys, 0) for c in ("sit", "stand")}

  for step in range(args.steps):
    with torch.inference_mode():
      obs, _, dones, _ = env.step(policy(obs))
    flag = base.command_manager.get_command("twist")[:, 0] > 0.5
    changed = (flag != prev_flag) | dones.bool()
    since = torch.where(changed, torch.zeros_like(since), since + 1)
    prev_flag = flag

    z = robot.data.root_link_pos_w[:, 2]
    tilt = torch.rad2deg(torch.acos((-robot.data.projected_gravity_b[:, 2]).clamp(-1, 1)))
    head_down = robot.data.body_link_pos_w[:, head_ids, 2].min(dim=1).values < HEAD_DOWN_Z
    leaned = (tilt >= 25.0) & (tilt <= 60.0)
    lying = tilt > 60.0
    ok_sit = ((z - SIT_Z).abs() < args.tol) & (tilt < 25.0) & ~head_down
    ok_stand = ((z - STAND_Z).abs() < args.tol) & (tilt < 20.0) & ~head_down
    valid = since >= settle
    if args.log_every and step % args.log_every == 0:
      print(f"[pose] step={step} sit_cmd:{int(flag.sum())} z_med={float(z.median()):.3f} "
            f"leaned:{int(leaned.sum())} lying:{int(lying.sum())} head_down:{int(head_down.sum())} / {n}")
    for name, m, ok, wrong in (
      ("sit", valid & flag, ok_sit, z > 0.10),
      ("stand", valid & ~flag, ok_stand, z < 0.08),
    ):
      s = stats[name]
      s["samples"] += int(m.sum())
      s["ok"] += int((m & ok).sum())
      s["leaned"] += int((m & leaned).sum())
      s["lying"] += int((m & lying).sum())
      s["head_down"] += int((m & head_down).sum())
      s["wrong"] += int((m & wrong).sum())

  res = {"task": args.task, "checkpoint": args.checkpoint, "num_envs": n, "steps": args.steps,
         "curriculum_iter": args.curriculum_iter, "cfg": "train" if args.train_cfg else "play",
         "settle_s": args.settle_s, "tol": args.tol, "warmup": "one auto-reset", "pins": args.pin}
  for name, s in stats.items():
    k = max(s["samples"], 1)
    res[name] = {"samples": s["samples"], **{f"{key}_frac": s[key] / k for key in keys[1:]}}
  print("[eval_sitstand] " + json.dumps(res, ensure_ascii=False))
  if args.json:
    with open(args.json, "w") as f:
      json.dump(res, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
  main()
