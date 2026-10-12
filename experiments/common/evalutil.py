"""評価スクリプト共通: 環境と方策を用意し、学習時と同じ「自動リセット後」の状態から測定を始める。

注意（2026-10-12 に判明）: runner.load() はチェックポイントに保存された common_step_counter
（例: model_2999 なら 72000）も環境に書き戻す。カリキュラムは reset 時にこのカウンタで段階を決めるので、
読み込みの「前」に段階を設定すると最初のエピソードだけその段階、自動リセット以降は学習終了時の段階になる
（以前の評価で「最初のエピソードだけ挙動が違う」と見えた原因）。
→ 読み込みの「後」に common_step_counter を設定し、全 env を reset してから測る。
"""

from __future__ import annotations

from dataclasses import asdict

import torch

from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.tasks.registry import load_env_cfg, load_rl_cfg, load_runner_cls
from mjlab.utils.torch import configure_torch_backends

NUM_STEPS_PER_ENV = 24  # 1 iteration = 24 env step（カリキュラムの step 換算）


def make_env_and_policy(task: str, checkpoint: str, num_envs: int, curriculum_iter: int = 0,
                        train_cfg: bool = False, spacing: float | None = None, render: bool = False):
  configure_torch_backends()
  device = "cuda:0" if torch.cuda.is_available() else "cpu"
  env_cfg = load_env_cfg(task, play=not train_cfg)
  agent_cfg = load_rl_cfg(task)
  env_cfg.scene.num_envs = num_envs
  if spacing is not None:
    env_cfg.scene.env_spacing = spacing
    if env_cfg.scene.terrain is not None:
      env_cfg.scene.terrain.env_spacing = spacing
  base = ManagerBasedRlEnv(cfg=env_cfg, device=device, render_mode="rgb_array" if render else None)
  env = RslRlVecEnvWrapper(base, clip_actions=agent_cfg.clip_actions)
  runner_cls = load_runner_cls(task) or MjlabOnPolicyRunner
  runner = runner_cls(env, asdict(agent_cfg), device=device)
  runner.load(checkpoint, load_cfg={"actor": True}, strict=True, map_location=device)
  policy = runner.get_inference_policy(device=device)
  # load がチェックポイントのカウンタを書き戻すので、その後に段階を設定して全 env に反映する
  base.common_step_counter = curriculum_iter * NUM_STEPS_PER_ENV
  env.reset()
  return env_cfg, base, env, policy, device


def warmup_until_auto_reset(base, env, policy, max_steps: int | None = None):
  """全 env が少なくとも一度自動リセットされるまで方策で動かす。戻り値の obs は直後の状態。

  返り値: (obs, last_dones)。終了条件のないタスク（SitStand, StandUp）では全 env が同時に時間切れになるので、
  last_dones は全 True となり、obs は全 env が新しいエピソードを始めた瞬間の状態になる。
  """
  ep_steps = int(round(base.cfg.episode_length_s / base.step_dt))
  max_steps = max_steps or 3 * ep_steps
  reset_once = torch.zeros(base.num_envs, dtype=torch.bool, device=base.device)
  obs = env.get_observations()
  dones = reset_once
  for _ in range(max_steps):
    with torch.inference_mode():
      obs, _, dones, _ = env.step(policy(obs))
    reset_once |= dones.bool()
    if bool(reset_once.all()):
      break
  else:
    raise RuntimeError("warm-up: 自動リセットされない env がある")
  return obs, dones.bool()
