"""起き上がり方策の成功率を初期姿勢別にヘッドレス評価する（描画なし）。

N 体を 1 エピソード動かして捨て（手動リセット直後は挙動が学習時と異なるため）、全 env が同時に自動リセットされた
次のエピソードを測る（初期姿勢はタスクの reset イベントが決める）。1 エピソード分動かして、
終了直前に「立てているか」（胴体の傾き < --upright-deg かつ 胴体高さ > --min-height）を判定する。
初期姿勢は reset 直後の重力方向から分類する:
  upright   : 傾き < 45°（座位など）
  face_down : 横倒し以上 かつ 機体前方 (+x) が下
  face_up   : 横倒し以上 かつ 機体前方が上
  side      : 横倒し以上 かつ 横方向 (y) 成分が支配的

使い方（microduck_rl ディレクトリで）:
  uv run python ../../experiments/common/eval_standup.py --task Mjlab-StandUp-Flat-MicroDuck \
      --checkpoint path/to/model_N.pt --num-envs 2048 --curriculum-iter 5000
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
  p.add_argument("--num-envs", type=int, default=2048)
  p.add_argument("--curriculum-iter", type=int, default=0,
                 help="この iteration 時点のカリキュラム（初期姿勢の混合・外乱）で評価")
  p.add_argument("--train-cfg", action="store_true", help="play ではなく学習用の env 設定を使う")
  p.add_argument("--upright-deg", type=float, default=20.0)
  p.add_argument("--min-height", type=float, default=0.10, help="立位とみなす胴体高さ [m]（立位 ≈ 0.115〜0.12）")
  p.add_argument("--all-prone", action="store_true",
                 help="VelStand 用: 全 env を寝た姿勢（うつ伏せ/仰向け/横向き）から開始し、時間切れ以外の終了を外す")
  p.add_argument("--json", default=None)
  args = p.parse_args()

  def all_prone(cfg):
    stage = {"step": 0, "params": {"prone_prob": 1.0, "face_down_prob": 0.5, "side_prob": 0.5, "crouch_prob": 0.0}}
    cfg.curriculum["prone_init_prob"].params["param_stages"] = [stage]
    for name in list(cfg.terminations):
      if name != "time_out":
        del cfg.terminations[name]

  env_cfg, base, env, policy, device = make_env_and_policy(
    args.task, args.checkpoint, args.num_envs, args.curriculum_iter, args.train_cfg,
    cfg_hook=all_prone if args.all_prone else None)
  # 1 エピソード捨てる。全 env が同時に時間切れになるので、戻った obs は全 env の新エピソード開始時点
  obs, dones = warmup_until_auto_reset(base, env, policy)
  if not bool(dones.all()):
    raise RuntimeError("全 env が同時にリセットされていない（終了条件のあるタスクには未対応）")
  robot = base.scene["robot"]

  # 初期姿勢の分類（自動リセット直後）
  g = robot.data.projected_gravity_b.clone()
  tilt0 = torch.rad2deg(torch.acos((-g[:, 2]).clamp(-1, 1)))
  lying = tilt0 >= 45.0
  side = lying & (g[:, 1].abs() > g[:, 0].abs())
  face_down = lying & ~side & (g[:, 0] > 0)  # 前方 +x が重力方向（下）を向く
  face_up = lying & ~side & (g[:, 0] <= 0)
  groups = {"upright": ~lying, "face_down": face_down, "face_up": face_up, "side": side}

  ep_steps = int(round(env_cfg.episode_length_s / base.step_dt))
  t_first_up = torch.full((args.num_envs,), -1, device=device)
  cos_up = math.cos(math.radians(args.upright_deg))
  for t in range(ep_steps - 2):  # 時間切れ reset の直前で止める
    with torch.inference_mode():
      obs, _, _, _ = env.step(policy(obs))
    up = (-robot.data.projected_gravity_b[:, 2] > cos_up) & (robot.data.root_link_pos_w[:, 2] > args.min_height)
    t_first_up = torch.where((t_first_up < 0) & up, torch.full_like(t_first_up, t), t_first_up)

  final_up = up
  res = {
    "task": args.task, "checkpoint": args.checkpoint, "num_envs": args.num_envs,
    "curriculum_iter": args.curriculum_iter, "cfg": "train" if args.train_cfg else "play",
    "episode_s": env_cfg.episode_length_s, "upright_deg": args.upright_deg, "min_height": args.min_height,
    "warmup": "one auto-reset", "all_prone": args.all_prone, "overall_success": float(final_up.float().mean()),
    "groups": {},
  }
  for name, m in groups.items():
    k = int(m.sum())
    if k == 0:
      continue
    reached = t_first_up[m] >= 0
    res["groups"][name] = {
      "n": k,
      "success_at_end": float(final_up[m].float().mean()),
      "ever_stood": float(reached.float().mean()),
      "median_time_to_stand_s": float(t_first_up[m][reached].float().median() * base.step_dt) if reached.any() else None,
    }
  print("[eval_standup] " + json.dumps(res, ensure_ascii=False))
  if args.json:
    with open(args.json, "w") as f:
      json.dump(res, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
  main()
