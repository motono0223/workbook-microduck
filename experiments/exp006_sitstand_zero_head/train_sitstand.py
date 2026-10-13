"""exp006 ランチャー: SitStand の頭部指令に「ゼロ指令バケット」を足してから mjlab の train を起動する。

exp002 の切り分けで、頭部指令がほぼゼロだと「座れ」指令の約 1/3 を無視することが分かった（学習後半は頭部指令が
常に大きく振られ、頭を静止したまま座る経験が少ない）。UniformPoseCommandCfg.zero_command_prob（公式実装済み,
SitStand では 0）を HEAD_ZERO_PROB に設定する。サブモジュールは編集しない。

  HEAD_ZERO_PROB=0.3 python train_sitstand.py Mjlab-SitStand-Flat-MicroDuck [train の引数...]
"""

import os
import sys

import mjlab_microduck.tasks  # noqa: F401  タスク登録
from mjlab.tasks import registry


def main() -> None:
  prob = float(os.environ.get("HEAD_ZERO_PROB", "0.3"))
  task = sys.argv[1]
  entry = registry._REGISTRY[task]
  for cfg in (entry.env_cfg, entry.play_env_cfg):
    cfg.commands["head_pose"].zero_command_prob = prob
  print(f"[train_sitstand] head_pose.zero_command_prob = {prob}")

  from mjlab.scripts.train import main as train_main
  train_main()


if __name__ == "__main__":
  main()
