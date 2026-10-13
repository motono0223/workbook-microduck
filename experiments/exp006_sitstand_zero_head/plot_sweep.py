"""exp002 と exp006 のチェックポイント別評価（eval/ckpt_sweep/*.json）を 1 枚の図にする。"""

import glob
import json
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RUNS = {
  "exp002 (baseline)": "exp002_sitstand/outputs/2026-10-12_01-19-41_exp002",
  "exp006 (zero head cmd 30%)": "exp006_sitstand_zero_head/outputs/2026-10-13_04-34-48_exp006",
}
COLORS = {"exp002 (baseline)": "#2a78d6", "exp006 (zero head cmd 30%)": "#eb6834"}
SURFACE, TEXT, TEXT_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
PANELS = [("calm", "sit", "Sit success - no perturbation, head still"),
          ("final", "sit", "Sit success - final-stage perturbations"),
          ("final", "stand", "Stand success - final-stage perturbations")]


def load(run_dir, cond, key):
  pts = []
  for f in glob.glob(os.path.join(ROOT, run_dir, "eval/ckpt_sweep", f"model_*_{cond}.json")):
    it = int(re.search(r"model_(\d+)_", f).group(1))
    pts.append((it, json.load(open(f))[key]["ok_frac"] * 100))
  return sorted(pts)


fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
fig.patch.set_facecolor(SURFACE)
for ax, (cond, key, title) in zip(axes, PANELS):
  ax.set_facecolor(SURFACE)
  for si, (name, run) in enumerate(RUNS.items()):
    pts = load(run, cond, key)
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=COLORS[name], linewidth=2, marker="o", markersize=6,
            markeredgecolor=SURFACE, markeredgewidth=1.5, label=name)
    ax.annotate(f"{ys[-1]:.0f}%", (xs[-1], ys[-1]), xytext=(6, -7 if si == 0 else 7), textcoords="offset points",
                va="center", fontsize=8, color=TEXT_2)
  ax.set_title(title, fontsize=10, color=TEXT, loc="left")
  ax.set_xlabel("checkpoint (iteration)", fontsize=8, color=TEXT_2)
  ax.set_ylim(0, 105)
  ax.set_xlim(900, 3250)
  for s in ("top", "right"):
    ax.spines[s].set_visible(False)
  for s in ("left", "bottom"):
    ax.spines[s].set_color(GRID)
  ax.tick_params(colors=TEXT_2, labelsize=8, length=0)
  ax.grid(True, color=GRID, linewidth=0.6)
  ax.set_axisbelow(True)
axes[0].set_ylabel("success [%]", fontsize=8, color=TEXT_2)
axes[0].legend(frameon=False, fontsize=8, loc="lower right", labelcolor=TEXT)
fig.suptitle("SitStand checkpoint sweep (512 robots each, eval_sitstand.py)", fontsize=12, color=TEXT, x=0.01, ha="left")
fig.tight_layout(rect=(0, 0, 1, 0.94))
out = os.path.join(ROOT, "exp006_sitstand_zero_head/outputs/2026-10-13_04-34-48_exp006/plots/ckpt_sweep_vs_exp002.png")
fig.savefig(out, dpi=130, facecolor=SURFACE)
print("wrote", out)
