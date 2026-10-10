"""tensorboard ログから学習曲線の PNG と全スカラーの CSV を書き出す。

使い方:
  python experiments/common/plot_training.py <run_dir> [--out <dir>] [--smooth 0.98]
  （run_dir は events.out.tfevents.* を含む rsl_rl の run ディレクトリ）

出力（既定: <run_dir>/../plots/）:
  01_overview.png      報酬・エピソード長・速度追従誤差・転倒・方策の探索幅
  02_reward_terms.png  報酬項ごとの推移（青=報酬, 橙=ペナルティ）
  03_curriculum.png    カリキュラム変数
  04_optimization.png  PPO の損失・学習率・スループット
  05_gait_metrics.png  歩容系の指標
  scalars.csv          全スカラー（iteration x tag）
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

# dataviz リファレンスパレット（light）
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
BLUE = "#2a78d6"  # 報酬 / 既定
ORANGE = "#eb6834"  # ペナルティ

OVERVIEW = [
  ("Train/mean_reward", "Mean episode reward"),
  ("Train/mean_episode_length", "Mean episode length [steps]"),
  ("Metrics/twist/error_vel_xy", "Linear velocity error [m/s]"),
  ("Metrics/twist/error_vel_yaw", "Yaw rate error [rad/s]"),
  ("Episode_Termination/fell_over", "Fell-over terminations"),
  ("Policy/mean_std", "Policy action std"),
]
OPTIM = [
  ("Loss/value", "Value loss"),
  ("Loss/surrogate", "Surrogate loss"),
  ("Loss/entropy", "Entropy"),
  ("Loss/learning_rate", "Learning rate"),
  ("Perf/total_fps", "Throughput [env steps/s]"),
  ("Perf/collection_time", "Rollout time per iter [s]"),
]


def load_scalars(run_dir: Path) -> dict[str, tuple[np.ndarray, np.ndarray]]:
  files = sorted(glob.glob(str(run_dir / "events.out.tfevents.*")))
  if not files:
    raise FileNotFoundError(f"no tfevents in {run_dir}")
  data: dict[str, tuple[np.ndarray, np.ndarray]] = {}
  for f in files:
    ea = EventAccumulator(f, size_guidance={"scalars": 0})
    ea.Reload()
    for tag in ea.Tags()["scalars"]:
      ev = ea.Scalars(tag)
      data[tag] = (np.array([e.step for e in ev]), np.array([e.value for e in ev]))
  return data


def ema(y: np.ndarray, alpha: float) -> np.ndarray:
  out = np.empty_like(y, dtype=float)
  acc = y[0]
  for i, v in enumerate(y):
    acc = alpha * acc + (1 - alpha) * v
    out[i] = acc
  return out


def style_axes(ax) -> None:
  ax.set_facecolor(SURFACE)
  for s in ("top", "right"):
    ax.spines[s].set_visible(False)
  for s in ("left", "bottom"):
    ax.spines[s].set_color(GRID)
  ax.tick_params(colors=TEXT_2, labelsize=8, length=0)
  ax.grid(True, color=GRID, linewidth=0.6)
  ax.set_axisbelow(True)


def plot_panel(ax, steps, values, title, color, smooth, step_like=False) -> None:
  style_axes(ax)
  if step_like:
    ax.step(steps, values, where="post", color=color, linewidth=2)
  else:
    ax.plot(steps, values, color=color, linewidth=0.8, alpha=0.25)
    ax.plot(steps, ema(values, smooth), color=color, linewidth=2)
  ax.set_title(title, fontsize=9.5, color=TEXT, loc="left")
  ax.set_xlabel("iteration", fontsize=8, color=TEXT_2)
  ax.margins(x=0.01)


def grid_figure(panels, data, title, out, smooth, ncols=3, step_like=False):
  panels = [(t, *rest) for t, *rest in panels if t in data]
  nrows = int(np.ceil(len(panels) / ncols))
  fig, axes = plt.subplots(nrows, ncols, figsize=(4.2 * ncols, 2.9 * nrows), squeeze=False)
  fig.patch.set_facecolor(SURFACE)
  for ax, (tag, label, *color) in zip(axes.flat, panels):
    s, v = data[tag]
    plot_panel(ax, s, v, label, color[0] if color else BLUE, smooth, step_like)
  for ax in list(axes.flat)[len(panels):]:
    ax.set_visible(False)
  fig.suptitle(title, fontsize=12, color=TEXT, x=0.01, ha="left")
  fig.tight_layout(rect=(0, 0, 1, 0.97))
  fig.savefig(out, dpi=130, facecolor=SURFACE)
  plt.close(fig)
  print(f"[plot_training] wrote {out}")


def main() -> None:
  p = argparse.ArgumentParser()
  p.add_argument("run_dir", type=Path)
  p.add_argument("--out", type=Path, default=None)
  p.add_argument("--smooth", type=float, default=0.98, help="EMA 係数（太線）")
  args = p.parse_args()

  run_dir = args.run_dir.resolve()
  out = (args.out or run_dir.parent / "plots").resolve()
  out.mkdir(parents=True, exist_ok=True)
  data = load_scalars(run_dir)
  name = run_dir.name
  sm = args.smooth

  grid_figure(OVERVIEW, data, f"{name} - overview (thin: raw, thick: EMA {sm})",
              out / "01_overview.png", sm)

  terms = []
  for tag in sorted(t for t in data if t.startswith("Episode_Reward/")):
    v = data[tag][1]
    penalty = np.median(v[len(v) // 2:]) < 0
    label = tag.split("/", 1)[1] + (" (penalty)" if penalty else "")
    terms.append((tag, label, ORANGE if penalty else BLUE))
  grid_figure(terms, data, f"{name} - reward terms per episode (blue: reward, orange: penalty)",
              out / "02_reward_terms.png", sm, ncols=4)

  curr = [(t, t.split("/", 1)[1]) for t in sorted(data) if t.startswith("Curriculum/")]
  grid_figure(curr, data, f"{name} - curriculum", out / "03_curriculum.png", sm,
              ncols=4, step_like=True)

  grid_figure(OPTIM, data, f"{name} - PPO optimization", out / "04_optimization.png", sm)

  gait = [(t, t.split("/", 1)[1]) for t in sorted(data)
          if t.startswith("Metrics/") and not t.startswith("Metrics/twist")]
  gait += [("Episode_Metrics/mean_action_acc", "mean_action_acc")]
  grid_figure(gait, data, f"{name} - gait metrics", out / "05_gait_metrics.png", sm)

  # 表形式（全スカラー）
  tags = sorted(t for t in data if not t.endswith("/time"))
  steps = sorted({int(s) for t in tags for s in data[t][0]})
  idx = {s: i for i, s in enumerate(steps)}
  table = np.full((len(steps), len(tags)), np.nan)
  for j, t in enumerate(tags):
    for s, v in zip(*data[t]):
      table[idx[int(s)], j] = v
  with open(out / "scalars.csv", "w") as f:
    f.write("iteration," + ",".join(tags) + "\n")
    for s, row in zip(steps, table):
      f.write(f"{s}," + ",".join("" if np.isnan(x) else f"{x:.6g}" for x in row) + "\n")
  print(f"[plot_training] wrote {out / 'scalars.csv'}")


if __name__ == "__main__":
  main()
