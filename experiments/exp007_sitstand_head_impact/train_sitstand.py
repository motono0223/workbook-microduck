"""exp007 ランチャー: exp006（頭部指令のゼロ指令バケット）に「頭部の床衝撃ペナルティ」を足して train を起動する。

exp002 の方策は座るたびに頭部前面（jaw_soft）を床について支え、その接触力は 11〜71 N に達した。
公式 SitStand は頭と床の接触を罰していない（頭で支える座り方を許可）が、公式 VelStand は頭部の床反力 15 N 超を
危険とみなし body_impact_cost でペナルティ化している（顔からの転倒は約 60 N）。同じ仕組みを SitStand に入れる:
  - 接触センサー: 頭部ボディ（neck, neck_pitch, yaw_roll_motion, jaw_soft）↔ terrain の合力。
    公式 HEAD_BODY_NAMES にある bearing_roll は右股関節リンク（公式コメントで誤記と明記）なので除外する
    （座ると股関節が床に近づくため、含めると座る動作そのものを罰してしまう）
  - 報酬 head_impact = body_impact_cost(threshold=15 N): 15 N を超えた分 [N] × 重み（静かに頭を添える ~7 N は無料）
  - 重みは最初 25%（座る動作の発見を妨げない）、HEAD_IMPACT_FULL_ITER から 100%（公式 VelStand と同じ段階導入）
サブモジュールは編集しない。
"""

import os
import sys

import mjlab_microduck.tasks  # noqa: F401  タスク登録
from mjlab.managers import CurriculumTermCfg, RewardTermCfg
from mjlab.sensor import ContactMatch, ContactSensorCfg
from mjlab.tasks import registry
from mjlab_microduck.tasks import mdp as microduck_mdp

HEAD_BODIES = ("neck", "neck_pitch", "yaw_roll_motion", "jaw_soft")
NUM_STEPS_PER_ENV = 24


def apply(cfg, zero_prob: float, weight: float, thresh: float, full_iter: int, stage0_frac: float) -> None:
  cfg.commands["head_pose"].zero_command_prob = zero_prob
  sensor = ContactSensorCfg(
    name="head_ground_contact",
    primary=ContactMatch(mode="body", pattern=rf"^({'|'.join(HEAD_BODIES)})$", entity="robot"),
    secondary=ContactMatch(mode="body", pattern="terrain"),
    fields=("force",),
    reduce="netforce",
    num_slots=1,
  )
  cfg.scene.sensors = tuple(cfg.scene.sensors) + (sensor,)
  cfg.rewards["head_impact"] = RewardTermCfg(
    func=microduck_mdp.body_impact_cost,
    weight=weight * stage0_frac,
    params={"sensor_name": sensor.name, "threshold": thresh},
  )
  cfg.curriculum["head_impact_weight"] = CurriculumTermCfg(
    func=microduck_mdp.reward_weight,
    params={
      "reward_name": "head_impact",
      "weight_stages": [
        {"step": 0, "weight": weight * stage0_frac},
        {"step": full_iter * NUM_STEPS_PER_ENV, "weight": weight},
      ],
    },
  )


def main() -> None:
  zero_prob = float(os.environ.get("HEAD_ZERO_PROB", "0.3"))
  weight = float(os.environ.get("HEAD_IMPACT_WEIGHT", "-0.02"))
  thresh = float(os.environ.get("HEAD_IMPACT_THRESH_N", "15.0"))
  full_iter = int(os.environ.get("HEAD_IMPACT_FULL_ITER", "750"))
  stage0 = float(os.environ.get("HEAD_IMPACT_STAGE0_FRAC", "0.25"))
  task = sys.argv[1]
  entry = registry._REGISTRY[task]
  for cfg in (entry.env_cfg, entry.play_env_cfg):
    apply(cfg, zero_prob, weight, thresh, full_iter, stage0)
  print(f"[train_sitstand] zero_command_prob={zero_prob} head_impact weight={weight} (x{stage0} until iter {full_iter}) "
        f"threshold={thresh} N bodies={HEAD_BODIES}")

  from mjlab.scripts.train import main as train_main
  train_main()


if __name__ == "__main__":
  main()
