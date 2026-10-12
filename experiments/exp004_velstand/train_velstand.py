"""VelStand 用ランチャー: 先生役チェックポイントを手元のファイルに差し替えてから mjlab の train を起動する。

公式の VelStand は distill.py の bc_cfg で 2 つの凍結教師を wandb (pollen-robotics) から取得する:
  - stand expert（倒れた状態のフレームを教える）  : 69u48n8l @ model_9750
  - walk anchor  （立っているフレームを元の歩行に固定）: 441tzs6d @ model_3750
これを環境変数で渡したローカルの .pt に置き換える（サブモジュールは編集しない）。

  STAND_EXPERT_CKPT=<exp003 の model_N.pt> WALK_ANCHOR_CKPT=<exp001 の model_N.pt> \
    python train_velstand.py Mjlab-VelStand-Flat-MicroDuck [train の引数...]
"""

import os
import sys
from pathlib import Path

import mjlab_microduck.tasks  # noqa: F401  タスク登録
from mjlab.tasks import registry


def main() -> None:
  stand = Path(os.environ["STAND_EXPERT_CKPT"]).resolve()
  walk = Path(os.environ["WALK_ANCHOR_CKPT"]).resolve()
  for p in (stand, walk):
    if not p.is_file():
      sys.exit(f"[train_velstand] checkpoint not found: {p}")

  task = sys.argv[1]
  bc = registry._REGISTRY[task].rl_cfg.algorithm.bc_cfg
  if bc is None:
    sys.exit(f"[train_velstand] {task} has no bc_cfg (ENABLE_EXPERT_BC is off?)")
  bc.update(
    checkpoint_path=str(stand), wandb_run_path=None,
    anchor_checkpoint_path=str(walk), anchor_wandb_run_path=None,
  )
  print(f"[train_velstand] stand expert: {stand}")
  print(f"[train_velstand] walk anchor : {walk}")

  from mjlab.scripts.train import main as train_main
  train_main()


if __name__ == "__main__":
  main()
