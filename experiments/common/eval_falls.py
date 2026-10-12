"""学習済み方策の転倒率を多数の個体でヘッドレス評価する（描画なし）。

動画 1 本では偶然か傾向か判断できないため、N 体を T ステップ動かし、胴体の傾きから転倒を数える。
カリキュラムは play 設定だと step 0（最も易しい段階）から始まるので、--curriculum-iter で
学習の任意の段階（例: 最終段）の外乱・指令範囲を再現できる。
測定は全 env が一度自動リセットされた後から（evalutil 参照。手動リセット直後は挙動が学習時と異なる）。

使い方（microduck_rl ディレクトリで）:
  uv run python ../../experiments/common/eval_falls.py --task Mjlab-SitStand-Flat-MicroDuck \
      --checkpoint path/to/model_N.pt --num-envs 1024 --steps 1000 --curriculum-iter 3000
"""

from __future__ import annotations

import argparse
import json
import math

import torch

from evalutil import make_env_and_policy, warmup_until_auto_reset


def main() -> None:
  p = argparse.ArgumentParser()
  p.add_argument("--task", required=True)
  p.add_argument("--checkpoint", required=True)
  p.add_argument("--num-envs", type=int, default=1024)
  p.add_argument("--steps", type=int, default=1000, help="制御ステップ数（50Hz）")
  p.add_argument("--curriculum-iter", type=int, default=0,
                 help="この iteration 時点のカリキュラム（外乱・指令範囲）で評価。0 = play と同じ最易段")
  p.add_argument("--train-cfg", action="store_true",
                 help="play 用ではなく学習用の env 設定を使う（play は押し外乱の間隔などが異なる）")
  p.add_argument("--fall-deg", type=float, default=60.0, help="この傾きを超えたら転倒とみなす")
  p.add_argument("--json", default=None, help="結果を JSON で保存")
  args = p.parse_args()

  _, base, env, policy, device = make_env_and_policy(
    args.task, args.checkpoint, args.num_envs, args.curriculum_iter, args.train_cfg)
  obs, _ = warmup_until_auto_reset(base, env, policy)

  robot = base.scene["robot"]
  cos_fall = math.cos(math.radians(args.fall_deg))
  n = args.num_envs
  ever_fallen = torch.zeros(n, dtype=torch.bool, device=device)
  was_fallen = torch.zeros(n, dtype=torch.bool, device=device)
  fall_events = 0
  fallen_steps = 0
  cmd_at_fall: list[float] = []
  has_twist = "twist" in base.command_manager.active_terms

  for _ in range(args.steps):
    with torch.inference_mode():
      obs, _, dones, _ = env.step(policy(obs))
    # 胴体の傾き: 機体座標系での重力方向の z 成分（直立で -1）
    tilt_cos = -robot.data.projected_gravity_b[:, 2]
    fallen = tilt_cos < cos_fall
    new_fall = fallen & ~was_fallen
    fall_events += int(new_fall.sum())
    if has_twist and new_fall.any():
      cmd_at_fall += base.command_manager.get_command("twist")[new_fall, 0].tolist()
    ever_fallen |= fallen
    fallen_steps += int(fallen.sum())
    was_fallen = fallen & ~dones.bool()  # reset された env は転倒状態を解除

  minutes = n * args.steps * base.step_dt / 60.0
  res = {
    "task": args.task, "checkpoint": args.checkpoint, "num_envs": n, "steps": args.steps,
    "curriculum_iter": args.curriculum_iter, "cfg": "train" if args.train_cfg else "play",
    "fall_deg": args.fall_deg, "warmup": "one auto-reset",
    "ever_fallen_frac": float(ever_fallen.float().mean()),
    "fallen_time_frac": fallen_steps / (n * args.steps),
    "falls_per_robot_minute": fall_events / minutes,
    "fall_events": fall_events,
  }
  if cmd_at_fall:
    res["falls_cmd_vx_mean"] = sum(cmd_at_fall) / len(cmd_at_fall)
    res["falls_with_cmd_vx_gt_0.5_frac"] = sum(v > 0.5 for v in cmd_at_fall) / len(cmd_at_fall)
  print("[eval_falls] " + json.dumps(res, ensure_ascii=False))
  if args.json:
    with open(args.json, "w") as f:
      json.dump(res, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
  main()
