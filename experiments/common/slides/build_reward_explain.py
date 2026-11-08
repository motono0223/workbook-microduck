"""Build reward_explain.json (formulas read from code; curves computed from exact formulas)."""
import json, math

OUT = "/tmp/claude-1000/-home-motono0223-workbook-microduck/8ff51f3e-8b95-4780-9109-c7a36e929232/scratchpad/deck/reward_explain.json"
TERMS = "/tmp/claude-1000/-home-motono0223-workbook-microduck/8ff51f3e-8b95-4780-9109-c7a36e929232/scratchpad/deck/reward_terms.json"


def curve(f, lo, hi, n=21):
    xs = [lo + (hi - lo) * i / (n - 1) for i in range(n)]
    return [[round(float(x), 6), round(float(f(x)), 6)] for x in xs]


def smoothstep(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


deg = math.radians
E = {}


def add(name, func, formula, symbols, gate, returns, what, why, stype, x, params, crv, evidence):
    if crv == [] and "note" not in params:
        raise ValueError(name + " needs note")
    p = dict(params)
    E[name] = {
        "func": func, "formula": formula, "symbols": symbols, "gate": gate,
        "returns": returns, "what": what, "why": why,
        "shape": {"type": stype, "x": x, "params": p, "curve": crv},
        "evidence": evidence,
    }


R, C, S = "reward", "cost(>=0, negative weight)", "self-negating(<=0, positive weight)"

# ---------------- mjlab velocity terms ----------------
s2 = 0.1  # std = sqrt(0.1)
add("track_linear_velocity", "track_linear_velocity",
    "r = exp(−(‖v_cmd,xy − v_xy‖² + v_z²) / σ²),  σ² = 0.1 (σ=√0.1≈0.316)",
    "v_cmd,xy: 指令並進速度 [m/s]、v_xy, v_z: 胴体(root link)の実速度 [m/s]（いずれもボディ座標系）。v_z は指令 0 とみなし誤差に加算",
    "",
    R,
    "指令された前後・左右速度にどれだけ追従しているかを測り、上下方向の揺れ(v_z)も誤差として含める。",
    "歩行タスクの主目的。microduck cfg で weight=2.0・std²=0.1 に設定（velstand も同値）。",
    "gauss", "速度誤差 ‖Δv‖ [m/s]", {"sigma": math.sqrt(s2), "sigma_sq": s2, "xmax": 1.0},
    curve(lambda e: math.exp(-e * e / s2), 0, 1.0),
    "xy_error = torch.sum(torch.square(command[:, :2] - actual[:, :2]), dim=1); z_error = torch.square(actual[:, 2]); return torch.exp(-lin_vel_error / std**2)")

s2 = 0.5
add("track_angular_velocity", "track_angular_velocity",
    "r = exp(−((ω_cmd,z − ω_z)² + ω_x² + ω_y²) / σ²),  σ² = 0.5 (σ=√0.5≈0.707)",
    "ω_cmd,z: 指令ヨーレート [rad/s]、ω: 胴体角速度 [rad/s]（ボディ座標系）。ロール/ピッチ角速度は指令 0 とみなし誤差に加算",
    "",
    R,
    "指令ヨーレートへの追従度。歩行で生じるロール・ピッチ方向の回転も誤差として減点する。",
    "旋回指令への追従が主目的。cfg で weight=2.0・std²=0.5。velstand コメントによれば σ=0.71 は小誤差に甘く、その場旋回の不感帯の一因と分析されている。",
    "gauss", "角速度誤差 [rad/s]", {"sigma": math.sqrt(s2), "sigma_sq": s2, "xmax": 2.0},
    curve(lambda e: math.exp(-e * e / s2), 0, 2.0),
    "z_error = torch.square(command[:, 2] - actual[:, 2]); xy_error = torch.sum(torch.square(actual[:, :2]), dim=1); return torch.exp(-ang_vel_error / std**2)")

s2 = 0.05
add("upright", "upright（velstand: upright_body_cmd_relative）",
    "r = exp(−‖g_b,xy‖² / σ²),  σ² = 0.05。g_b: 胴体座標系の重力単位ベクトル, ‖g_b,xy‖² = sin²θ",
    "g_b,xy: trunk_base 座標系に投影した重力方向の水平成分（無次元）、θ: 胴体の鉛直からの傾き [rad]",
    "常時。velstand では upright_body_cmd_relative に差し替え: 目標 g_b,xy=(sinθ_cmd, −sinφ_cmd·cosθ_cmd)（body_pose 指令のロール/ピッチ）からの誤差で評価",
    R,
    "胴体がどれだけ水平(直立)を保っているか。傾きの二乗に対するガウス型。",
    "cfg コメント: 歩行時に前傾 2〜4° が常態化し、速度中の押し転倒の約 2/3 が前方だったため weight 1.0/σ²=0.1 から 2.0/σ²=0.05 に強化（4° 前傾で約 0.19/step の損失）。",
    "gauss", "胴体の傾き θ [deg]", {"sigma_sq": s2, "xmax_deg": 45},
    curve(lambda t: math.exp(-math.sin(deg(t)) ** 2 / s2), 0, 45),
    "projected_gravity_b = quat_apply_inverse(body_quat_w, gravity_w); xy_squared = torch.sum(torch.square(projected_gravity_b[:, :2]), dim=1); return torch.exp(-xy_squared / std**2)")

add("pose", "variable_posture（velstand: variable_posture_body_relaxed）",
    "r = exp(−mean_j((q_j − q_j^home)² / σ_j²))。σ_j は速度レジームで切替: 静止(s<0.01) / 歩行(0.01≤s<1.5) / 走行(s≥1.5)",
    "q_j: 脚関節角 [rad]（passive/neck/head を除く）、q^home: 既定姿勢、s = ‖v_cmd,xy‖+|ω_cmd,z|。σ静止: hip_yaw .1, hip_roll .05, hip_pitch .15, knee .15, ankle .1",
    "常時。σ歩行=走行: hip_yaw .3, hip_roll .05, hip_pitch .4, knee .4, ankle .25。velstand: 静止中に body_pose 指令(z/roll/pitch)が非ゼロなら σ_body（hip_roll .25 等）を使用",
    R,
    "脚の関節角が既定(HOME)姿勢からどれだけ離れているかを、関節ごとの許容幅 σ で正規化して測る。",
    "cfg コメント: 首/頭は head_pose_tracking が指令で動かすため除外（含めると HOME に引き戻す力と競合し、方策が頭部指令を無視するようになる）。静止時は狭い σ で姿勢を固定。",
    "gauss", "正規化関節誤差 |q−q^home|/σ（全関節同値と仮定）", {"note": "全関節の正規化誤差が等しいと仮定した曲線 y=exp(−x²)。実際は関節ごとに σ が異なる", "xmax": 2.5},
    curve(lambda u: math.exp(-u * u), 0, 2.5),
    "standing_mask = (total_speed < walking_threshold).float() ... return torch.exp(-torch.mean(error_squared / (std**2), dim=1))")

add("body_ang_vel", "body_angular_velocity_penalty",
    "c = ω_x² + ω_y²（ヨー軸 ω_z は罰しない）",
    "ω_x, ω_y: trunk_base の角速度 [rad/s]（ワールド座標系）",
    "",
    C,
    "胴体のロール・ピッチ方向の回転速度の二乗和。ふらつき・揺れを測る。",
    "胴体の揺れ抑制。AGENTS.md では『運動ブロッカー』に分類され、動的タスク(起き上がり等)では軽く保つべきとされ、全タスクで -0.05（velocity 値）に揃えている。",
    "quadratic", "胴体ロール/ピッチ角速度 |ω_xy| [rad/s]", {"xmax": 5.0},
    curve(lambda w: w * w, 0, 5.0),
    "ang_vel_xy = ang_vel[:, :2]  # Don't penalize z-angular velocity.\nreturn torch.sum(torch.square(ang_vel_xy), dim=1)")

add("angular_momentum", "angular_momentum_penalty",
    "c = ‖L‖²",
    "L: ロボット全体の角運動量 [kg·m²/s]（センサ robot/root_angmom の 3 次元値）",
    "",
    C,
    "全身の角運動量の大きさの二乗。手足や頭を振り回して生じる回転の勢いを測る。",
    "docstring は『自然な腕振りを促すため全身角運動量を罰する』。AGENTS.md では運動ブロッカーに分類され -0.02 と軽量。",
    "quadratic", "角運動量 ‖L‖ [kg·m²/s]", {"xmax": 0.1, "note": "x 範囲は図示用の仮定（実機スケール未計測）"},
    curve(lambda l: l * l, 0, 0.1),
    "angmom_magnitude_sq = torch.sum(torch.square(angmom), dim=-1)\nreturn angmom_magnitude_sq")

add("dof_pos_limits", "joint_pos_limits",
    "c = Σ_j [max(q_lo,j − q_j, 0) + max(q_j − q_hi,j, 0)]",
    "q_j: 関節角 [rad]、q_lo/q_hi: ソフト関節リミット（物理リミットより内側）。超過量の L1 和",
    "ソフトリミット内では 0",
    C,
    "関節角がソフトリミットを超えた量 [rad] の合計。",
    "関節が可動域の端に張り付くのを防ぐ。AGENTS.md: この標準項は可動域の最後の ~7.5% でしか発火しないので、張り付き対策には別途近接ペナルティが必要。",
    "relu", "ソフトリミット超過量 q−q_hi [rad]", {"note": "片側のみ図示。負側は 0", "xmax": 0.3},
    curve(lambda d: max(d, 0.0), -0.1, 0.3),
    "out_of_limits = -(joint_pos - soft_limits[..., 0]).clip(max=0.0); out_of_limits += (joint_pos - soft_limits[..., 1]).clip(min=0.0)")

add("action_rate_l2", "action_rate_l2（velstand: action_rate_l2_fallen_scaled）",
    "c = Σ_i (a_t,i − a_{t−1},i)²  （velstand: × 0.1 転倒中[tilt>40°]）",
    "a_t: 方策の生出力（スケール/オフセット適用前）、全アクション次元（脚+首）で和",
    "常時。velstand のみ tilt>40° の間 ×0.1（fallen_scale）",
    C,
    "前ステップからの行動の変化量の二乗和。指令のガタつきを測る滑らかさ項。",
    "実機転移のための平滑化。velocity では -0.1→-1.0 に curriculum で段階強化。velstand run-1 教訓: 転倒中も全額課金すると起き上がり試行が割に合わず『寝たまま』が最適になったので転倒中は 0.1 倍。",
    "quadratic", "1 次元あたりの行動変化 |Δa|", {"xmax": 1.0},
    curve(lambda d: d * d, 0, 1.0),
    "return torch.sum(torch.square(env.action_manager.action - env.action_manager.prev_action), dim=1)")

add("air_time", "feet_air_time（velstand: feet_air_time_upright）",
    "r = Σ_feet 1[0.125 < t_air < 0.3] × 1[‖v_cmd,xy‖+|ω_cmd,z| > 0.01]",
    "t_air: 各足の現在の滞空時間 [s]（接地センサ feet_ground_contact）、足 2 本で 0〜2",
    "指令の大きさ ‖v_cmd,xy‖+|ω_cmd,z| > 0.01 のときのみ。velstand は tilt>40°（転倒中）で 0",
    R,
    "各足が適切な時間(0.125〜0.3 s)だけ宙に浮いている状態を毎ステップ数える。足を上げて歩くことへの報酬。",
    "足を引きずらず周期的に踏み出させる主要な歩容報酬（weight 3.0）。velstand: 寝転んだまま足を振って窓内の滞空を稼ぐ『脚を振る』搾取が観測されたため転倒中は無効化。",
    "window", "1 本の足の滞空時間 t_air [s]", {"lo": 0.125, "hi": 0.3, "xmax": 0.5},
    curve(lambda t: 1.0 if 0.125 < t < 0.3 else 0.0, 0, 0.48, 25),
    "in_range = (current_air_time > threshold_min) & (current_air_time < threshold_max); reward = torch.sum(in_range.float(), dim=1) ... reward *= scale")

add("foot_clearance", "feet_clearance",
    "c = Σ_feet |h − 0.02| · ‖v_foot,xy‖ × 1[指令>0.01]",
    "h: 足裏の地形からの高さ [m]（foot_height_scan）、v_foot,xy: 足サイトの水平速度 [m/s]（ワールド）",
    "指令の大きさ ‖v_cmd,xy‖+|ω_cmd,z| > 0.01 のときのみ",
    C,
    "足が動いている(水平速度がある)間、足の高さが目標 2 cm からずれている量を速度で重み付けして測る。",
    "cfg コメント: target を 0.01→0.02 m に上げて足の引きずりを罰する。動いている足ほど高く上げることを促す。",
    "linear", "足の高さ h [m]（‖v_foot,xy‖=1 m/s のとき）", {"target_height": 0.02, "foot_speed": 1.0, "note": "値は足速度に比例。曲線は 1 m/s の場合"},
    curve(lambda h: abs(h - 0.02) * 1.0, 0, 0.05),
    "delta = torch.abs(foot_height - target_height); cost = torch.sum(delta * vel_norm, dim=1)")

add("foot_swing_height", "feet_swing_height",
    "c = Σ_feet (h_peak/0.02 − 1)² · 1[着地瞬間] × 1[指令>0.01]",
    "h_peak: 直前の遊脚期の最高到達高さ [m]（着地時に評価してリセット）",
    "着地した瞬間(first contact)のステップのみ、かつ指令 > 0.01",
    C,
    "1 歩ごとの足の最高到達高さが目標 2 cm からどれだけずれたかを、着地時に相対誤差の二乗で評価する。",
    "cfg コメント: target を 0.01→0.02 m に上げ、足をしっかり持ち上げさせる。",
    "quadratic", "遊脚期の最高高さ h_peak [m]", {"target_height": 0.02, "xmax": 0.05},
    curve(lambda h: (h / 0.02 - 1) ** 2, 0, 0.05),
    "error = self.peak_heights / target_height - 1.0; cost = torch.sum(torch.square(error) * first_contact.float(), dim=1) * active")

add("foot_slip", "feet_slip",
    "c = Σ_feet ‖v_foot,xy‖² · 1[接地] × 1[指令>0.01]",
    "v_foot,xy: 足サイトの水平速度 [m/s]（ワールド）、接地判定は feet_ground_contact",
    "接地中の足のみ、指令 > 0.01 のときのみ",
    C,
    "接地している足が地面上で滑っている速さの二乗。",
    "cfg コメント: weight -1.0 はこのロボットの軸足を使った旋回には厳しすぎたため、意図的に弱い -0.1。",
    "quadratic", "接地足の水平速度 [m/s]", {"xmax": 0.5},
    curve(lambda v: v * v, 0, 0.5),
    "cost = torch.sum(vel_xy_norm_sq * in_contact, dim=1) * active")

add("self_collisions", "self_collision_cost",
    "c = 自己接触の検出数（force_history なし → Σ found）",
    "found: 自己衝突センサ self_collision（trunk_base サブツリー同士）が検出した接触数",
    "",
    C,
    "脚と胴体（バッテリーホルダー等）がぶつかっている接触の数。",
    "cfg コメント: 脚が胴体のバッテリーホルダーに衝突するのを防ぐ。関節可動域で実際には届かないが、正の信号で十分な距離を保たせる。",
    "count", "自己接触数", {"note": "離散カウントのため曲線なし（値=接触数）"}, [],
    "assert data.found is not None\nreturn data.found.sum(dim=-1).float()")

s = 0.5
add("head_pose_tracking", "head_pose_tracking",
    "r = mean_{j∈首4関節} exp(−((q_j − q_j^home) − c_j)² / σ²),  σ = 0.5 rad",
    "c_j: head_pose 指令（既定姿勢からの差分 [rad]、順に neck_pitch, head_pitch, head_yaw, head_roll）、q_j: 実関節角（バックラッシュモデルでは出力側）",
    "常時（velocity/velstand weight 2.0、sitstand/standup 0.75）",
    R,
    "首・頭の 4 関節が指令角度にどれだけ合っているかを関節ごとのガウスで評価し平均する。",
    "cfg コメント: 頭部指令追従は velocity の主目的。σ=0.5 なら ±1 rad 指令で追従しなくても exp(−4)≈0.018 の勾配が残る。平均形式なので部分的な追従でも部分点（全か無かにならない）。",
    "gauss", "1 関節の追従誤差 [rad]", {"sigma": s, "xmax": 1.5},
    curve(lambda e: math.exp(-(e / s) ** 2), 0, 1.5),
    "err = actual - cmd\nper_joint = torch.exp(-(err / std) ** 2)\nreturn per_joint.mean(dim=-1)")

add("body_pose_tracking", "body_pose_tracking_6d（standup/velstand: body_pose_tracking_locomotion）",
    "r = (1/6)Σ_{x,y,z,roll,pitch,yaw} exp(−(e_k/σ_k)²); σ_xy=0.05 m, σ_z=0.02 m, σ_ang=15°, z目標=0.095+Δz",
    "e_k: body_pose 指令（x,y: スポーン原点からの差 [m], z: nominal_height からの差 [m], 角度: ZYX オイラー [rad]）と実姿勢の差",
    "velocity は weight 0（無効）。standup/velstand は locomotion 版: z・roll・pitch のみ(axis_weights=0,0,1,1,1,0)、σ_z=0.01, σ_ang=5°, z0=0.115/0.116、velstand は静止 env のみ(standing gate)",
    R,
    "胴体の位置・姿勢(6 自由度)が指令にどれだけ合っているかを軸ごとのガウスの平均で測る。",
    "velocity では観測スロットとコマンドを残すため weight 0 で配線のみ。velstand では静止中の胴体ロール/ピッチ指令追従のため weight 2.0（歩行には課金しない standing gate 付き）。",
    "composite", "軸ごとの誤差", {"note": "6 軸ガウスの平均（タスクで有効軸と σ が異なる）ため 1 次元曲線は省略", "xy_std": 0.05, "z_std": 0.02, "angle_std": deg(15)}, [],
    "r_z = torch.exp(-(z_err / z_std) ** 2) ...\nreturn (r_x + r_y + r_z + r_r + r_p + r_w) / 6.0")

add("head_pose_bias", "head_pose_bias_penalty",
    "r = −mean_j |EMA_τ(e_j)|,  EMA: m ← (1−α)m + α·e, α = dt/τ = 0.02 (τ=1 s)",
    "e_j: 首 4 関節の追従誤差 [rad]（head_pose_tracking と同定義）、EMA で 1 s 平均した直流成分（偏り）",
    "velocity は無ゲート（weight 0→curriculum で 3.0）。standup/velstand は z(0.09→0.11 m) と傾き(20°→45°/40°) の smoothstep ゲートを EMA 入力と出力の両方に掛ける",
    S,
    "頭部追従誤差の 1 秒平均（重力による垂れ下がりなどの定常的な偏り）の大きさ。",
    "cfg コメント: 頭が約 15° 下を向いて歩く問題の対策。head_pose_tracking の σ を絞ると歩行の揺れまで罰して方策が歩かなくなった(5yay13u4)。揺れは平均で打ち消し、回避可能な定常バイアスだけを L1 で課金する。",
    "linear", "定常バイアス誤差 |e| [rad]", {"tau_s": 1.0, "note": "誤差が一定のときの定常値（EMA 収束後）。過渡応答は時定数 1 s", "xmax": 0.5},
    curve(lambda e: -abs(e), 0, 0.5),
    "alpha = min(1.0, float(env.step_dt) / max(tau_s, 1e-6)); env._head_bias_ema = (1.0 - alpha) * env._head_bias_ema + alpha * err; out = -env._head_bias_ema.abs().mean(dim=-1)")

# ---------------- sitstand ----------------
SITGATE = "SitStand コマンドの slew された目標 α（0=STAND, 1=SIT、2 s で一定速度で遷移）に追従"
s = 0.5
add("posture_pose_legs", "posture_pose_match",
    "r = mean_{j∈脚10関節} exp(−((q_j − q_j*(α))/σ)²),  σ = 0.5,  q*(α) = q^home + α(q^sit − q^home)",
    "q_j: 脚関節角 [rad]、q^sit: 座りキーフレーム（膝 ±1.35 rad 等）、α: slew 済み目標ブレンド（0=立, 1=座）",
    "常時（目標が α で座り/立ち姿勢間を補間）",
    R,
    "脚の関節角が、指令された姿勢（座り or 立ち、遷移中は補間）の目標にどれだけ合っているか。",
    "cfg コメント: 脚のみ（頭は指令で操作）。σ を広めにして、膝 ~1.35 rad 差のどちら側からも勾配が残るようにしている。",
    "gauss", "1 関節の目標誤差 [rad]", {"sigma": s, "xmax": 1.5},
    curve(lambda e: math.exp(-(e / s) ** 2), 0, 1.5),
    "target = stand_target + blend.unsqueeze(-1) * (sit_target - stand_target)\nreturn torch.exp(-((joint_pos - target) / std) ** 2).mean(dim=-1)")

add("posture_pose_l1", "posture_pose_l1",
    "r = −mean_{j∈脚10関節} |q_j − q_j*(α)|",
    "q_j*(α): posture_pose_legs と同じ補間目標 [rad]",
    "常時",
    S,
    "脚関節の目標からのずれの平均絶対値（L1）。",
    "cfg コメント: L1 ブートストラップ — 目標から遠くても一定の勾配を与える（ガウスは遠方で平坦になるため）。",
    "linear", "平均関節誤差 [rad]", {"xmax": 1.5},
    curve(lambda e: -abs(e), 0, 1.5),
    "return -torch.abs(joint_pos - target).mean(dim=-1)")

for nm, s, why in [
    ("posture_height", 0.04, "cfg コメント: 2 層ガウスの広い層。55 mm の座り↔立ちの移動全体にわたってブートストラップの引き込みを与える。"),
    ("posture_height_sharp", 0.015, "cfg コメント: 2 層ガウスの鋭い層。最後の 1 cm でも飽和せず実際の勾配が出るようにする（standup の教訓）。"),
]:
    add(nm, "posture_height_gaussian",
        f"r = exp(−((z − z*(α))/σ)²),  σ = {s} m,  z*(α) = 0.115 + α(0.06 − 0.115)",
        "z: 胴体(root)の高さ [m]（env 原点の地形高さ基準）、z*: slew 済み目標高さ（立 0.115 m / 座 0.06 m）",
        "常時（目標高さが α に追従）",
        R,
        "胴体の高さが指令姿勢の目標高さにどれだけ近いか。",
        why,
        "gauss", "高さ誤差 z − z* [m]", {"sigma": s, "sit_z": 0.06, "stand_z": 0.115},
        curve(lambda d, s=s: math.exp(-(d / s) ** 2), -2 * s, 2 * s),
        "target_z = stand_z + blend * (sit_z - stand_z)\nreturn torch.exp(-((z - target_z) / std) ** 2)")

add("posture_height_l1", "posture_height_l1",
    "r = −|z − z*(α)|,  z*(α) = 0.115 + α(0.06 − 0.115)",
    "z: 胴体高さ [m]、z*: slew 済み目標高さ [m]",
    "常時",
    S,
    "胴体高さの目標からのずれの絶対値 [m]。",
    "cfg/docstring: 遷移の駆動役。間違った姿勢で休むと毎ステップ ~55 mm 分の一定コストがかかり、『指令を無視する』戦略を両方向で損にする（weight 6.0）。",
    "linear", "高さ誤差 z − z* [m]", {"xmin": -0.06, "xmax": 0.06},
    curve(lambda d: -abs(d), -0.06, 0.06),
    "return -torch.abs(z - target_z)")

add("rise_bootstrap", "posture_rise_bootstrap",
    "r = clip(v_z, 0, 0.08) · 1[z < 0.125] · (1 − sit)",
    "v_z: 胴体の鉛直速度 [m/s]（ワールド）、z: 胴体高さ [m]、sit: 生の座り指令フラグ（0/1、slew 前）",
    "STAND 指令中(sit=0)かつ z < 0.125 m のときのみ。SIT 指令中は常に 0",
    R,
    "立ち指令中に胴体が上昇している速さ（0.08 m/s で頭打ち）。",
    "docstring: 目的地だけの報酬は静止時に勾配ゼロで『座ったまま L1 を払う』局所解になる（standup 環境の教訓）。上昇動作そのものに報酬を払い、上限で爆発的な立ち上がりが得にならないようにする。",
    "relu", "胴体の鉛直速度 v_z [m/s]", {"max_vz": 0.08, "max_height": 0.125, "note": "STAND 指令かつ z<0.125 の場合の曲線"},
    curve(lambda v: min(max(v, 0.0), 0.08), -0.05, 0.15),
    "return torch.clamp(vz, min=0.0, max=max_vz) * (z < max_height).float() * (1.0 - sit)")

add("descent_speed", "trunk_downward_velocity_penalty",
    "r = −max(−v_z − 0.05, 0)",
    "v_z: 胴体の鉛直速度 [m/s]（ワールド、下向きが負）",
    "常時（0.05 m/s より遅い下降・上昇は 0）",
    S,
    "胴体が 0.05 m/s より速く下降している超過分。",
    "cfg コメント: 座り動作の『乱暴さ』防止の本命。速い落下は毎ステップ課金されるので償却できない。符号注意: 関数自体が負を返すので weight は正(+10)。負重みにした run 7ev90yd9 は暴力的な動きが報酬になり尻もち跳ねを学習した。",
    "relu", "胴体の鉛直速度 v_z [m/s]", {"max_down_vel": 0.05},
    curve(lambda v: -max(-v - 0.05, 0.0), -0.3, 0.1),
    "return -torch.clamp(-vz - max_down_vel, min=0.0)")

add("rise_speed", "trunk_upward_velocity_penalty",
    "r = −max(v_z − 0.08, 0)",
    "v_z: 胴体の鉛直速度 [m/s]（ワールド、上向き正）",
    "常時だが weight は 0 から開始し curriculum（iter 750）で導入",
    S,
    "胴体が 0.08 m/s より速く上昇している超過分。",
    "cfg コメント: 立ち上がり用の速度上限。技能の発見中に動作課金を入れると試行が損になり技能が見つからない（standup の教訓）ので、上昇動作の発見後に curriculum で導入。",
    "relu", "胴体の鉛直速度 v_z [m/s]", {"max_up_vel": 0.08},
    curve(lambda v: -max(v - 0.08, 0.0), -0.1, 0.3),
    "return -torch.clamp(vz - max_up_vel, min=0.0)")

add("gentle_motion", "trunk_vertical_accel_penalty",
    "r = −|a_z|,  a_z = (v_z,t − v_z,t−1)/dt  (dt = 0.02 s)",
    "a_z: 胴体鉛直加速度 [m/s²]（鉛直速度の制御周期差分）。エピソード開始ステップは 0",
    "常時（リセット直後のステップのみ 0）",
    S,
    "胴体の上下方向の加速度の大きさ。着地の衝撃や急な動きを捉える。",
    "docstring: 着地時の減速スパイクを捉え、等速の静かな下降(a_z≈0)を促す。座って静止していれば 0。cfg: 符号注意で正の重み(+0.05)。",
    "linear", "胴体鉛直加速度 a_z [m/s²]", {"xmin": -20, "xmax": 20},
    curve(lambda a: -abs(a), -20, 20),
    "a_z = (vz - prev) / env.step_dt ... return -torch.abs(a_z)")

add("upright_linear", "body_upright_linear",
    "r = cos θ = 1 − 2(q_x² + q_y²)",
    "θ: 胴体(root link)の鉛直からの傾き、q: 胴体姿勢クォータニオン [w,x,y,z]（ワールド）。直立 +1、水平 0、倒立 −1",
    "常時（sitstand/standup ではゲートなし）",
    R,
    "胴体がどれだけ直立しているかを cosθ で線形に測る。",
    "docstring: ガウス型と違いどの傾きでも勾配がある（うつ伏せからでも起き上がる方向の信号）。sitstand cfg: 両方の静止姿勢で胴体を立てる常時床。2.5 で『仰向けで寝る』が直立静止より約 4.5/step 劣る。",
    "other", "胴体の傾き θ [deg]", {"note": "y = cos θ"},
    curve(lambda t: math.cos(deg(t)), 0, 180),
    "reward = 1.0 - 2.0 * (qx * qx + qy * qy)")

add("upright_while_tall", "upright_while_tall",
    "r = cos θ · smoothstep((z − 0.075)/(0.1 − 0.075)),  smoothstep(t)=t²(3−2t), t∈[0,1]",
    "θ: 胴体の傾き、z: 胴体高さ [m]",
    "z ≤ 0.075 m で 0、z ≥ 0.10 m で全額（その間は smoothstep）",
    R,
    "背が高い（まだ立っている）間だけ効く直立報酬。",
    "docstring/cfg: 高い位置のまま後ろへ傾いて倒れ込み、下降報酬を稼ぐ『制御された転倒』を防ぐ。座った後（尻が床）は傾きを許容。",
    "smoothstep_gate", "胴体高さ z [m]（θ=0 のとき）", {"lo": 0.075, "hi": 0.1, "note": "θ=0（cosθ=1）の場合のゲート曲線。実際は cosθ 倍"},
    curve(lambda z: float(smoothstep((z - 0.075) / 0.025)), 0.06, 0.115),
    "t = torch.clamp((z - height_low) / max(height_high - height_low, 1e-6), 0.0, 1.0); smooth = t * t * (3.0 - 2.0 * t); return upright * smooth")

add("posture_stillness", "posture_stillness",
    "r = exp(−(‖v‖/0.05)²) · G_z · G_tilt · 1[|sit − α| < 0.02]",
    "‖v‖: 胴体並進速度の大きさ [m/s]、G_z = smoothstep((0.03 − |z − z*|)/0.018)、G_tilt = smoothstep((cosθ − cos60°)/(cos25° − cos60°))",
    "目標高さ ±12 mm 内で全額・±30 mm で 0、傾き 25° 以下で全額・60° で 0、目標ランプ完了時のみ（遷移中は 0）",
    R,
    "指令姿勢の高さに到達し直立している状態で、胴体がどれだけ静止しているか。",
    "docstring/cfg: 『到着したら静かに直立で休む』を明示的な正のピークにする。傾きゲートで仰向け・うつ伏せ・横倒しでの静止（sit run-2 の搾取）には払わない。",
    "composite", "胴体速度 ‖v‖ [m/s]（全ゲート=1 のとき）", {"vel_std": 0.05, "band_full": 0.012, "band_zero": 0.03, "tilt_full_deg": 25, "tilt_zero_deg": 60, "note": "全ゲートが開いた(=1)場合の速度ガウス"},
    curve(lambda v: math.exp(-(v / 0.05) ** 2), 0, 0.15),
    "return torch.exp(-((v / vel_std) ** 2)) * z_gate * tilt_gate * ramp_done")

add("posture_composite", "posture_composite",
    "r = exp(−((z−z*)/0.03)²) · exp(−(1−cosθ)/0.4²) · exp(−mean(Δq_leg²)/0.4²) · exp(−mean(Δq_head²)/0.4²)",
    "z*: slew 済み目標高さ、θ: 胴体傾き、Δq_leg: 脚 10 関節の補間目標との差 [rad]、Δq_head: 首 4 関節の head_pose 指令との差 [rad]",
    "常時（積なので 1 因子でも外れると全体が ~0）",
    R,
    "高さ・直立・脚姿勢・頭姿勢の 4 つが同時に目標に合っているときだけ高い値になる積型のゴールスコア。",
    "cfg コメント: 部分和での妥協（板状・転倒・傾き・1 cm 手前で停止）を潰す。head 因子は、頭を床に垂らして休む方策（頭以外は全部目標どおり）が出たため追加。",
    "composite", "各因子の誤差", {"height_std": 0.03, "upright_std": 0.4, "pose_std": 0.4, "head_std": 0.4, "note": "4 因子の積のため 1 次元曲線は省略"}, [],
    "score = height_score * upright_score * pose_score ... score = score * torch.exp(-head_err_sq / (head_std * head_std))")

add("joint_torque_rate_l2", "joint_torque_rate_l2（velstand: joint_torque_rate_l2_fallen_scaled）",
    "c = Σ_i (τ_i,t − τ_i,t−1)²  （velstand: × 0.1 転倒中[tilt>40°]）",
    "τ_i: 各アクチュエータの出力トルク [N·m]、前の制御ステップとの差",
    "sitstand/standup は weight 0（curriculum で後から導入）。velstand は tilt>40° の間 ×0.1",
    C,
    "アクチュエータトルクの変化率の二乗和（ギアボックスへの衝撃の代理指標）。",
    "docstring: 着地衝撃などのトルクスパイクを罰し、ギアを守る柔らかい力の移行を促す。AGENTS.md: 平滑化項は技能発見の後に導入すべき（発見中の課金は『何もしない』を勝たせる）。",
    "quadratic", "1 アクチュエータのトルク変化 |Δτ| [N·m]", {"xmax": 0.5},
    curve(lambda d: d * d, 0, 0.5),
    "rate = current - env._prev_actuator_forces\nreturn torch.sum(torch.square(rate), dim=1)")

add("neck_strain_leaned", "neck_torque_when_tilted",
    "c = mean_{首4}(τ/0.1)² · clip((θ − 12°)/(25° − 12°), 0, 1) · 1[g_b,x < 0] · α",
    "τ: 首・頭アクチュエータのトルク [N·m]、θ: 胴体傾き（射影重力から）、g_b,x<0: 後ろ傾き、α: 座り目標ブレンド",
    "SIT 目標(α>0)・後ろ傾き・傾き 12° 超でのみ（25° 以上で全額、線形ランプ）",
    C,
    "座った状態で後ろに傾いたとき、首が重い頭を支えて出しているトルクの大きさ。",
    "cfg コメント: 実機で座り中に頭を急に動かすと後ろに倒れ、首サーボが過負荷になる。過負荷トルク 0.15 Nm で ≈ −1.1/step、直立・立ち・起立中・前傾では 0 なので発見を妨げず最初から有効。",
    "quadratic", "首トルク |τ| [N·m]（ゲート=1 のとき）", {"torque_scale": 0.1, "tilt_start_deg": 12, "tilt_full_deg": 25, "note": "後ろ傾き 25° 以上・α=1 の場合"},
    curve(lambda t: (t / 0.1) ** 2, 0, 0.2),
    "cost = torch.square(tau / torque_scale).mean(dim=1) ... gate = gate * (g[:, 0] < 0.0).float() * _posture_blend(env, command_name)")

add("head_impact", "body_impact_cost",
    "c = max(‖F_head‖ − 15, 0)",
    "F_head: 頭部ボディ群と地形との接触合力 [N]（head_ground_contact センサ, netforce）",
    "15 N 以下は 0。sitstand は exp007 ランチャーで追加（submodule の cfg には無い）、velstand は submodule 標準",
    C,
    "頭部が床に当たったときの接触力のうち 15 N を超えた分 [N]。",
    "velstand cfg: 頭で床を押して起き上がる準静的な ~7 N は無料、顔からの転倒(~60 N)だけを課金するため閾値 15 N。exp007: 座るたびに頭を床について支える方策（11〜71 N）を抑えるため SitStand にも導入。",
    "relu", "頭部の床接触力 [N]", {"threshold": 15.0},
    curve(lambda f: max(f - 15.0, 0.0), 0, 60),
    "total_force = forces.sum(dim=1); force_mag = torch.norm(total_force, dim=1); return torch.clamp(force_mag - threshold, min=0.0)")

# ---------------- standup ----------------
s = 0.5
add("pose_stand_legs", "pose_target_match",
    "r = mean_{j∈脚10関節} exp(−((q_j − q_j^home)/σ)²),  σ = 0.5",
    "q_j: 脚関節角 [rad]、q^home: HOME（立ち）姿勢（target_overrides=None）",
    "常時",
    R,
    "脚の関節角が立ち姿勢(HOME)にどれだけ近いか。",
    "cfg コメント: 単一の固定目標（立ち姿勢）を t=0 から与え、起き上がり経路は方策に発見させる（AGENTS.md: キーフレーム軌道は方策が途中で停滞する）。",
    "gauss", "1 関節の目標誤差 [rad]", {"sigma": s, "xmax": 1.5},
    curve(lambda e: math.exp(-(e / s) ** 2), 0, 1.5),
    "return torch.exp(-((joint_pos - target) / std) ** 2).mean(dim=-1)")

add("pose_stand_l1", "pose_l1_penalty",
    "r = −mean_{j∈脚10関節} |q_j − q_j^home|",
    "q_j: 脚関節角 [rad]、q^home: HOME 姿勢",
    "常時",
    S,
    "脚関節の HOME からのずれの平均絶対値。",
    "cfg コメント: 遠くても一定勾配の L1。収束時に ~0.18 rad（主に膝曲げ）残る問題に対し重みを上げ、残りの関節も閉じさせる。",
    "linear", "平均関節誤差 [rad]", {"xmax": 1.5},
    curve(lambda e: -abs(e), 0, 1.5),
    "return -torch.abs(joint_pos - target).mean(dim=-1)")

for nm, s, why in [
    ("height_stand", 0.04, "cfg コメント: 2 層ガウスの広い層（std 0.04）。座った状態からのブートストラップの引き込み。"),
    ("height_stand_sharp", 0.015, "cfg コメント: 以前の run は広いガウスが飽和(0.93)して z≈0.109 で止まった。鋭い層で最後の 1 cm に約 3 倍の引き込みを作る。"),
]:
    add(nm, "height_target_gaussian",
        f"r = exp(−((z − 0.115)/σ)²),  σ = {s} m",
        "z: 胴体(root)高さ [m]（env 原点の地形高さ基準）、0.115 m: 立ち姿勢の目標高さ",
        "常時",
        R,
        "胴体の高さが立ち高さ 0.115 m にどれだけ近いか。",
        why,
        "gauss", "胴体高さ z [m]", {"sigma": s, "target_height": 0.115},
        curve(lambda z, s=s: math.exp(-((z - 0.115) / s) ** 2), 0.03, 0.15),
        "return torch.exp(-((z - target_height) / std) ** 2)")

add("height_stand_l1", "height_l1_penalty",
    "r = −|z − 0.115|",
    "z: 胴体高さ [m]",
    "常時",
    S,
    "胴体高さの立ち目標からのずれ [m]。",
    "cfg コメント: 座ったままの静止が正味プラスになって停滞したため L1 を強化し『座り続ける』をコスト化（÷4 スケール後 weight 7.5）。",
    "linear", "胴体高さ z [m]", {"target_height": 0.115},
    curve(lambda z: -abs(z - 0.115), 0.03, 0.15),
    "return -torch.abs(z - target_height)")

add("com_upward_velocity", "com_upward_velocity",
    "r = max(v_z, 0) · 1[z < 0.125]  （velstand: × 1[tilt > 40°]）",
    "v_z: 胴体の鉛直速度 [m/s]（ワールド）、z: 胴体高さ [m]。standup では上限 max_vz なし",
    "z < 0.125 m のときのみ。velstand は転倒中(tilt>40°)のみで weight 0→curriculum で 2.0",
    R,
    "胴体が上昇している速さ（立ち高さ未満のときだけ）。",
    "cfg コメント: 目的地だけの報酬では『座って直立のまま部分点』が支配的な局所解だった。上昇動作自体に払い、どんな起立試行も即座にプラスにする。max_height を 0.125 にして最後の 1 cm も払う。上限 max_vz は回復の発見を壊したので撤廃。",
    "relu", "胴体の鉛直速度 v_z [m/s]", {"max_height": 0.125, "note": "z<0.125 の場合の曲線（上限なし）"},
    curve(lambda v: max(v, 0.0), -0.2, 0.5),
    "reward = torch.clamp(vz, min=0.0, max=max_vz) * below_target")

add("gentle_rise", "trunk_vertical_accel_penalty",
    "r = −|a_z|,  a_z = (v_z,t − v_z,t−1)/dt  (dt = 0.02 s)",
    "a_z: 胴体鉛直加速度 [m/s²]。エピソード開始ステップは 0",
    "常時。velstand は weight を 25%→100% に curriculum で増加",
    S,
    "胴体の上下方向の加速度の大きさ（衝撃・急な上下動）。",
    "standup cfg: com_upward_velocity と組み合わせて等速の滑らかな起立を選ばせる。うつ伏せからの反転でも課金されるので小さく保つ。符号注意: 以前の -0.005 は二重否定で衝撃への報酬になっていた。",
    "linear", "胴体鉛直加速度 a_z [m/s²]", {"xmin": -20, "xmax": 20},
    curve(lambda a: -abs(a), -20, 20),
    "a_z = (vz - prev) / env.step_dt ... return -torch.abs(a_z)")

add("arrival_damping", "body_ang_vel_at_height",
    "c = (ω_x² + ω_y²) · smoothstep((z − 0.09)/0.02) · smoothstep((45° − θ)/(45° − 20°))",
    "ω_x, ω_y: 胴体角速度 [rad/s]（ワールド）、z: 胴体高さ [m]、θ: 胴体傾き [deg]",
    "z ≤ 0.09 m または θ ≥ 45° で 0、z ≥ 0.11 m かつ θ ≤ 20° で全額。weight は 0 から開始（iter 3000 で curriculum 導入）",
    C,
    "立ち高さ付近でほぼ直立しているときだけの胴体の揺れ（ロール/ピッチ角速度の二乗）。",
    "cfg コメント: 実機の『起立→垂直を行き過ぎ→倒れる→再試行』ループを減衰させる。傾きゲートがないと前屈からの最後の伸び上がり自体を課金して手前で止まる。発見期に課金すると回復が学べないので後から導入。",
    "quadratic", "胴体ロール/ピッチ角速度 |ω_xy| [rad/s]（ゲート=1 のとき）", {"height_low": 0.09, "height_high": 0.11, "tilt_full_deg": 20, "tilt_zero_deg": 45, "note": "z≥0.11 かつ θ≤20° の場合"},
    curve(lambda w: w * w, 0, 3.0),
    "cost = torch.sum(torch.square(ang_vel[:, :2]), dim=1) ... gate = gate * (s * s * (3.0 - 2.0 * s)); return cost * gate")

add("upright_sharp", "upright_gaussian_at_height",
    "r = exp(−(1 − cosθ)/0.3²) · smoothstep((z − 0.06)/(0.115 − 0.06))",
    "θ: 胴体傾き（2(q_x²+q_y²) = 1−cosθ）、z: 胴体高さ [m]",
    "z ≤ 0.06 m で 0、z ≥ 0.115 m で全額",
    R,
    "立ち高さにいるときだけ効く、ほぼ垂直付近で勾配が強いガウス型直立報酬。",
    "cfg コメント: 線形 cosθ は垂直付近で勾配が弱く、以前の run は ~37° 後傾で収束した。高さゲートで『低く屈んで垂直』の搾取を防ぐ。std 0.1→0.3 に広げ、傾き盆地でも見える勾配を残す。",
    "gauss", "胴体の傾き θ [deg]（z ≥ 0.115 のとき）", {"std": 0.3, "height_low": 0.06, "height_high": 0.115, "note": "高さゲート=1 の場合"},
    curve(lambda t: math.exp(-(1 - math.cos(deg(t))) / 0.09), 0, 90),
    "tilt_sq = 2.0 * (qx * qx + qy * qy); upright_g = torch.exp(-tilt_sq / (std * std)) ... return upright_g * smooth")

add("standing_composite", "standing_composite_score",
    "r = exp(−((z−0.115)/0.04)²) · exp(−(1−cosθ)/0.4²) · exp(−mean(Δq_leg²)/0.4²)",
    "z: 胴体高さ [m]、θ: 胴体傾き、Δq_leg: 脚 10 関節の HOME との差 [rad]",
    "常時（積なので 1 因子でも外れると ~0）",
    R,
    "高さ・直立・脚姿勢の 3 つが同時に立ち姿勢に合っているときだけ高くなる積型ゴールスコア。",
    "docstring/cfg: 加算報酬の妥協盆地（正しい高さで胴体を傾ける）を壊す。以前の狭い std では盆地で ~5e-5 となり勾配が見えなかったため広げた。",
    "composite", "各因子の誤差", {"height_std": 0.04, "upright_std": 0.4, "pose_std": 0.4, "note": "3 因子の積のため 1 次元曲線は省略"}, [],
    "return height_score * upright_score * pose_score")

# ---------------- velstand ----------------
add("upright_progress", "upright_progress",
    "r = cosθ_t − cosθ_{t−1}（ポテンシャル差分）",
    "θ_t: 現ステップの胴体傾き（cosθ = 1−2(q_x²+q_y²)）。リセット直後は差分 0",
    "常時（ゲートなし）",
    R,
    "1 ステップで胴体がどれだけ直立方向へ近づいたか（離れれば負）。",
    "docstring/cfg: 転倒状態に正の報酬をゲートすると座り・寝・頭三脚で搾取された(run 1/2/4)。差分型は保持では 0、起き上がりで正、転倒で負なので搾取不能（Ng らのポテンシャル整形）。",
    "potential", "傾きの変化 Δcosθ", {"note": "状態ではなく変化量に払うため曲線なし（r = Δcosθ、うつ伏せ→直立の累計 ≈ +1）"}, [],
    "delta = cos_tilt - env._upright_potential_prev\nenv._upright_potential_prev = cos_tilt.clone()\nreturn delta")

add("height_progress", "height_progress",
    "r = min(z_t, 0.115) − min(z_{t−1}, 0.115)（ポテンシャル差分）",
    "z_t: 胴体高さ [m]（env 原点基準）、上限 0.115 m でクリップ。リセット直後は差分 0",
    "常時（ゲートなし）",
    R,
    "1 ステップで胴体がどれだけ上昇したか（下降は負、0.115 m 以上は 0）。",
    "cfg コメント: 深いしゃがみ→立ちの最後の区間は主に高さの変化で傾き変化が小さく、他の報酬が平坦。差分型なので歩行の上下動は正味 0。うつ伏せ→立ち全体で Δ≈+0.065×30≈+2。",
    "potential", "高さの変化 Δz [m]", {"ceiling": 0.115, "note": "変化量に払うため曲線なし"}, [],
    "pot = torch.clamp(z, max=ceiling); delta = pot - env._height_potential_prev")

add("servo_impact", "body_impact_cost",
    "c = max(‖F_servo‖ − 2, 0)",
    "F_servo: 名前付きの XL330 サーボ筐体ジオム群と地形との接触合力 [N]（servo_ground_contact）",
    "2 N 以下は 0。weight は 25%→100% に curriculum",
    C,
    "サーボ筐体が床に当たったときの接触力のうち 2 N を超えた分 [N]。",
    "velstand docstring: 実機で XL330 のギアが壊れ続けている。筐体が着地を受けることがギア破損を招くため、筐体接触を直接課金する。",
    "relu", "サーボ筐体の床接触力 [N]", {"threshold": 2.0},
    curve(lambda f: max(f - 2.0, 0.0), 0, 20),
    "return torch.clamp(force_mag - threshold, min=0.0)")

add("trunk_impact", "body_impact_cost",
    "c = max(‖F_trunk‖ − 20, 0)",
    "F_trunk: trunk_base（胴体シェル）と地形との接触合力 [N]（trunk_ground_contact）",
    "20 N 以下は 0。weight は 25%→100% に curriculum",
    C,
    "胴体シェルが床に当たったときの接触力のうち 20 N を超えた分 [N]。",
    "velstand docstring: head_impact と同じ論理。体重程度の準静的な押し(~7 N)は無料にし、衝撃スパイクだけを課金する。",
    "relu", "胴体の床接触力 [N]", {"threshold": 20.0},
    curve(lambda f: max(f - 20.0, 0.0), 0, 80),
    "return torch.clamp(force_mag - threshold, min=0.0)")

add("servo_acc_spike", "servo_acc_spike_penalty",
    "c = Σ_servo max(|q̈| − 300, 0),  q̈ = (q̇_t − q̇_{t−1})/dt",
    "q̇: サーボ関節速度 [rad/s]（passive_ を除く）、q̈: 制御周期差分の関節加速度 [rad/s²]。リセット直後は 0",
    "|q̈| ≤ 300 rad/s² の関節は 0。weight は 25%→100% に curriculum",
    C,
    "衝撃でサーボ関節が急激に逆駆動されたときの加速度の超過分の合計。",
    "docstring: 反射ロータ慣性(減速比 ~288²)のため衝撃時の関節加速度がギア損傷の代理指標。押し転倒では戦略に関わらず 450〜550 rad/s² に達するので、方策の手段は『どこでどう着地するか』。",
    "relu", "1 関節の加速度 |q̈| [rad/s²]", {"acc_thresh": 300.0},
    curve(lambda a: max(a - 300.0, 0.0), 0, 800),
    "acc = (vel - prev) / env.step_dt ... return torch.clamp(acc.abs() - acc_thresh, min=0.0).sum(dim=1)")

add("servo_stall", "servo_stall_penalty",
    "c = #{servo : |τ| > 0.4 N·m かつ |q̇| < 0.5 rad/s}",
    "τ: アクチュエータトルク [N·m]、q̇: サーボ関節速度 [rad/s]",
    "weight は 25%→100% に curriculum",
    C,
    "強く押しているのに動いていない（ストール状態の）サーボの個数。",
    "docstring: 体の下に挟まれた肢をサーボが押し続けると歯欠け・過熱の原因（実機の『けいれん』）。静立の負荷は数 1e-2 N·m なので 0.4 は本当に詰まったときだけ発火。run 5-6: ×3 にすると起立が弾道的になり悪化。",
    "count", "ストール中のサーボ数", {"torque_thresh": 0.4, "vel_thresh": 0.5, "note": "離散カウントのため曲線なし"}, [],
    "stalled = (torque.abs() > torque_thresh) & (vel.abs() < vel_thresh)\nreturn stalled.float().sum(dim=1)")

add("fallen_tax", "fallen_state_penalty",
    "c = 1[武装中]: tilt > 40° で武装、tilt < 25° かつ z > 0.09 m で解除（ヒステリシス）",
    "tilt: 胴体傾き [deg]、z: 胴体高さ [m]。リセット時は非武装",
    "転倒（tilt>40°）で 1 になり、本当に立つ（tilt<25° かつ z>0.09）まで 1 のまま。weight 0→curriculum（iter 600）で −0.5",
    C,
    "転倒してから完全に立ち直るまでの間、毎ステップ 1 を返す定額の『転倒税』。",
    "docstring/cfg: これがないと寝たまま fallen_too_long のリセットを待つのが合理的だった（試行は行動・トルク課金がかかる）。ヒステリシスで 40° ゲート直下のしゃがみが無料の休憩所にならないようにする。",
    "binary", "転倒状態", {"gate_tilt_above_deg": 40, "release_tilt_below_deg": 25, "release_z_above": 0.09, "note": "状態機械（0/1）のため曲線なし"}, [],
    "env._fallen_tax_armed |= fallen\nenv._fallen_tax_armed &= ~up\nreturn env._fallen_tax_armed.float()")

add("recovery_success", "recovery_success",
    "r = 1（その瞬間のみ）: tilt>40° が 0.5 s 以上続いた後に tilt<25° かつ z>0.09 m に到達したステップ",
    "tilt: 胴体傾き [deg]、z: 胴体高さ [m]。発火後は再び転倒するまで再武装しない",
    "転倒 0.5 s 以上で武装、立ち直った瞬間 1 回だけ発火。weight 0→curriculum（iter 600）で +10",
    R,
    "転倒から完全に立ち直ったことに対する一回きりのボーナス。",
    "docstring/cfg: 密なゲート付き項に欠けている強い終点信号。以前の up_z=0.105 は方策の実際の立ち高さ(0.084〜0.096)より高く一度も発火しなかったため 0.09 に修正。ヒステリシスでゲート付近の振動では払わない。",
    "binary", "回復イベント", {"fallen_tilt_deg": 40, "min_fallen_s": 0.5, "up_tilt_deg": 25, "up_z": 0.09, "note": "一回きりのイベント（0/1）のため曲線なし"}, [],
    "fired = env._recovery_armed & up\nenv._recovery_armed &= ~fired\nreturn fired.float()")

# ---------- check coverage ----------
terms = json.load(open(TERMS))
missing = set(terms) - set(E)
extra = set(E) - set(terms)
assert not missing and not extra, (missing, extra)
for k, v in E.items():
    c = v["shape"]["curve"]
    assert c == [] or 15 <= len(c) <= 25, (k, len(c))
ordered = {k: E[k] for k in terms}
json.dump(ordered, open(OUT, "w"), ensure_ascii=False, indent=1)
print("wrote", len(ordered))
