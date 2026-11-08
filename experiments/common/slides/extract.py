"""各 run の params/*.yaml, train.log, plots/scalars.csv からスライド用の事実データを JSON に抜き出す。

usage: python extract.py <run_dir> <out.json> [tag ...]   （tag は学習曲線に載せる scalars.csv の列名）
"""

import csv
import json
import re
import sys

import yaml


class L(yaml.SafeLoader):
  pass


def _any(loader, suffix, node):
  if isinstance(node, yaml.SequenceNode):
    return loader.construct_sequence(node, deep=True)
  if isinstance(node, yaml.MappingNode):
    return loader.construct_mapping(node, deep=True)
  return loader.construct_scalar(node)


L.add_multi_constructor("tag:yaml.org,2002:python/", _any)
L.add_multi_constructor("!", _any)


def short_func(f):
  s = str(f)
  return s.split(":")[-1].split(".")[-1] if s else ""


def scalar_params(p, skip=("asset_cfg", "sensor_name", "command_name", "_tensor_cache")):
  out = {}
  for k, v in (p or {}).items():
    if k in skip:
      continue
    if isinstance(v, (int, float, str, bool)) or (isinstance(v, list) and len(v) <= 4 and all(isinstance(x, (int, float)) for x in v)):
      out[k] = v
  return out


def parse_log_tables(log):
  obs = {}
  for m in re.finditer(r"Active Observation Terms in Group: '(\w+)' \(shape: \((\d+),\)\)", log):
    group, total = m.group(1), int(m.group(2))
    rest = log[m.end():].split("\n")
    terms = []
    for line in rest[3:]:
      if line.startswith("+"):
        if terms:
          break
        continue
      cells = [c.strip() for c in line.strip("|").split("|")]
      if len(cells) == 3 and cells[0].isdigit():
        dim = int(re.findall(r"\d+", cells[2])[0]) if re.findall(r"\d+", cells[2]) else 0
        terms.append([cells[1], dim])
    obs[group] = {"total": total, "terms": terms}
  act = re.search(r"Active Action Terms \(shape: (\d+)\)", log)
  envs = re.search(r"Number of environments \| (\d+)", log)
  times = re.findall(r"Iteration time: ([\d.]+)s", log)
  elapsed = re.findall(r"Time elapsed: ([\d:]+)", log)
  last_it = re.findall(r"Learning iteration (\d+)/(\d+)", log)
  return {
    "obs": obs, "action_dim": int(act.group(1)) if act else None,
    "num_envs": int(envs.group(1)) if envs else None,
    "iter_time_s_mean": round(sum(map(float, times)) / len(times), 2) if times else None,
    "time_elapsed": elapsed[-1] if elapsed else None,
    "iterations": int(last_it[-1][0]) + 1 if last_it else None,
  }


def summarize_stage(stage):
  st = dict(stage)
  st.pop("step", None)
  return json.dumps(st, ensure_ascii=False)[:160]


def main():
  run, out, tags = sys.argv[1], sys.argv[2], sys.argv[3:]
  env = yaml.load(open(f"{run}/params/env.yaml"), Loader=L)
  agent = yaml.load(open(f"{run}/params/agent.yaml"), Loader=L)
  log = open(f"{run}/train.log", errors="ignore").read()

  d = parse_log_tables(log)
  sim = env.get("sim", {})
  d["sim"] = {
    "timestep": sim.get("mujoco", {}).get("timestep"),
    "decimation": env.get("decimation"),
    "episode_length_s": env.get("episode_length_s"),
    "iterations_solver": sim.get("mujoco", {}).get("iterations"),
    "terrain": (env.get("scene", {}).get("terrain") or {}).get("terrain_type"),
    "env_spacing": env.get("scene", {}).get("env_spacing"),
  }
  d["rewards"] = [{"name": n, "weight": r.get("weight"), "func": short_func(r.get("func")),
                   "params": scalar_params(r.get("params"))} for n, r in env["rewards"].items()]
  d["terminations"] = [{"name": n, "func": short_func(t.get("func")), "params": scalar_params(t.get("params"))}
                       for n, t in env["terminations"].items()]
  d["events"] = [{"name": n, "mode": e.get("mode"), "func": short_func(e.get("func")),
                  "params": scalar_params(e.get("params")), "interval_s": e.get("interval_range_s")}
                 for n, e in env["events"].items()]
  cmds = {}
  for n, c in env["commands"].items():
    cmds[n] = {k: c.get(k) for k in ("resampling_time_range", "ranges", "rel_standing_envs", "sit_prob", "zero_command_prob") if k in c}
  d["commands"] = json.loads(json.dumps(cmds, default=str))
  cur = []
  for n, c in (env.get("curriculum") or {}).items():
    p = c.get("params") or {}
    key = next((k for k, v in p.items() if k.endswith("_stages") and isinstance(v, list)), None)
    if key:
      stages = p[key]
      cur.append({"name": n, "first": summarize_stage(stages[0]), "last": summarize_stage(stages[-1]),
                  "first_raw": {k: v for k, v in stages[0].items() if k != "step"},
                  "last_raw": {k: v for k, v in stages[-1].items() if k != "step"},
                  "target": {k: v for k, v in p.items() if k in ("reward_name", "event_name", "command_name", "term_name")},
                  "last_iter": int(stages[-1].get("step", 0)) // 24, "n_stages": len(stages)})
    else:
      cur.append({"name": n, "first": "", "last": "", "last_iter": None, "n_stages": 0})
  d["curriculum"] = cur

  alg = agent["algorithm"]
  d["agent"] = {
    "algorithm": alg.get("class_name"),
    "actor_hidden": list(agent["actor"]["hidden_dims"]), "critic_hidden": list(agent["critic"]["hidden_dims"]),
    "activation": agent["actor"]["activation"], "obs_normalization": agent["actor"]["obs_normalization"],
    "init_std": agent["actor"]["distribution_cfg"]["init_std"],
    "num_steps_per_env": agent["num_steps_per_env"], "max_iterations": agent["max_iterations"],
    "save_interval": agent["save_interval"], "seed": agent["seed"],
    **{k: alg.get(k) for k in ("learning_rate", "schedule", "desired_kl", "gamma", "lam", "clip_param",
                               "entropy_coef", "value_loss_coef", "num_learning_epochs", "num_mini_batches",
                               "max_grad_norm", "use_clipped_value_loss")},
    "bc": {k: v for k, v in (alg.get("bc_cfg") or {}).items() if isinstance(v, (int, float, str)) and v is not None} if alg.get("bc_cfg") else None,
  }

  rows = list(csv.DictReader(open(f"{run}/plots/scalars.csv")))
  series = {}
  step = max(1, len(rows) // 120)
  for t in tags:
    xs, ys = [], []
    for i in range(0, len(rows), step):
      # 前後 step 行の平均（間引きのエイリアスを避ける）
      win = [float(r[t]) for r in rows[i:i + step] if r.get(t) not in (None, "")]
      if win:
        xs.append(int(rows[i]["iteration"]))
        ys.append(round(sum(win) / len(win), 5))
    series[t] = {"x": xs, "y": ys}
  d["series"] = series
  json.dump(d, open(out, "w"), ensure_ascii=False, indent=1)
  print(out, "obs", {g: v["total"] for g, v in d["obs"].items()}, "act", d["action_dim"], "rewards", len(d["rewards"]))


if __name__ == "__main__":
  main()
