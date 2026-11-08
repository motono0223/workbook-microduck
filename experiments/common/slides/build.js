// usage: node build.js <outDir> [expId ...]
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("/home/motono0223/.claude/skills/synced/bb3596e7-e18f-45fc-b461-8e629a706748_7bcd0061-cd98-491f-91eb-2f08c79bf4c3/pptx/scripts/apply_theme.js");
const { DECKS, REWARD_DESC, OBS_DESC, EVENT_DESC, TERM_DESC } = require("./content.js");

const HERE = __dirname;
const DATA = (n) => JSON.parse(fs.readFileSync(path.join(HERE, "data", n + ".json"), "utf8"));
const EV = JSON.parse(fs.readFileSync(path.join(HERE, "data", "evals.json"), "utf8"));
const b64 = (p) => "data:image/png;base64," + fs.readFileSync(p).toString("base64");
const imgSize = (p) => { // PNG の幅・高さ
  const buf = fs.readFileSync(p); return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
};

const THEME = {
  name: "Microduck RL",
  headFontFace: "Meiryo", bodyFontFace: "Meiryo",
  colors: {
    dk1: "1C2430", lt1: "FFFFFF", dk2: "26313F", lt2: "EEF1F5",
    accent1: "E4692A", accent2: "2B7A9B", accent3: "4E8F57", accent4: "C79A1E", accent5: "7D5BA6", accent6: "8A96A3",
    hlink: "2B7A9B", folHlink: "7D5BA6",
  },
};
const HEX = { text: "1C2430", muted: "5E6B78", grid: "DCE1E7", orange: "E4692A", teal: "2B7A9B", green: "4E8F57", gray: "8A96A3", light: "EEF1F5", dark: "26313F" };
const W = 13.333, H = 7.5, MX = 0.6;
const CONTENT_Y = 1.45;

function defineLayouts(pres, C, expId) {
  pres.defineSlideMaster({
    title: "TITLE_DARK", background: { color: HEX.dark },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: MX, y: 2.2, w: W - 2 * MX, h: 1.4, fontSize: 36, bold: true, color: C.background1, valign: "bottom", align: "left" }, text: "" } },
      { placeholder: { options: { name: "body", type: "body", x: MX, y: 3.75, w: W - 2 * MX, h: 0.8, fontSize: 20, color: "C9D3DE", valign: "top" }, text: "" } },
    ],
  });
  pres.defineSlideMaster({
    title: "CONTENT", background: { color: HEX.light === "" ? "FFFFFF" : "FFFFFF" },
    margin: [0.5, 0.6, 0.7, 0.6],
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: MX, y: 0.35, w: W - 2 * MX, h: 0.85, fontSize: 28, bold: true, color: C.text1, valign: "middle" }, text: "" } },
      { text: { text: `Microduck RL  |  ${expId}`, options: { x: MX, y: 7.0, w: 6, h: 0.3, fontSize: 10, color: HEX.muted, isTextBox: true, margin: 0 } } },
    ],
    slideNumber: { x: W - MX - 0.8, y: 7.0, w: 0.8, h: 0.3, fontSize: 10, color: HEX.muted, align: "right" },
  });
  pres.defineSlideMaster({
    title: "CLOSING_DARK", background: { color: HEX.dark },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: MX, y: 0.45, w: W - 2 * MX, h: 0.8, fontSize: 28, bold: true, color: C.background1, valign: "middle" }, text: "" } },
    ],
    slideNumber: { x: W - MX - 0.8, y: 7.0, w: 0.8, h: 0.3, fontSize: 10, color: "9AA7B5", align: "right" },
  });
}

// ---------- helpers ----------
const fmt = (x, d = 3) => (x === null || x === undefined) ? "-" : (Math.abs(x) >= 100 ? x.toFixed(0) : +x.toFixed(d) + "");
function content(pres, title, section) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  return s;
}
function card(s, C, x, y, w, h, name) {
  s.addShape("roundRect", { x, y, w, h, rectRadius: 0.08, fill: { color: C.background2 }, line: { color: C.background2 }, objectName: name });
}
function bullets(s, items, opt) {
  s.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })),
    { isTextBox: true, fontSize: 14, color: HEX.text, valign: "top", paraSpaceAfter: 6, ...opt });
}
function table(s, rows, opt) {
  const head = rows[0].map((t) => ({ text: t, options: { bold: true, fill: { color: HEX.light }, color: HEX.text } }));
  const body = rows.slice(1).map((r) => r.map((t) => (typeof t === "object" ? t : { text: String(t) })));
  s.addTable([head, ...body], { fontSize: 11, color: HEX.text, border: { type: "solid", pt: 0.5, color: HEX.grid }, valign: "middle", margin: [2, 5, 2, 5], ...opt });
}
const chartBase = (C) => ({
  catAxisLabelColor: HEX.muted, valAxisLabelColor: HEX.muted, catAxisLabelFontSize: 9, valAxisLabelFontSize: 9,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", titleFontFace: "+mn-lt", legendFontFace: "+mn-lt",
  valGridLine: { color: HEX.grid, size: 0.5 }, catGridLine: { style: "none" },
  titleColor: HEX.text, titleFontSize: 12, showTitle: true, legendFontSize: 10, legendColor: HEX.text,
});

// カリキュラムの段階を読みやすく
function stageText(raw) {
  if (!raw || Object.keys(raw).length === 0) return "-";
  if ("weight" in raw) return `重み ${fmt(raw.weight, 4)}`;
  const k = Object.keys(raw)[0]; const val = raw[k];
  const maxAbs = (o) => { let m = 0; JSON.stringify(o).replace(/-?\d+\.?\d*(e-?\d+)?/g, (n) => { m = Math.max(m, Math.abs(parseFloat(n))); return n; }); return m; };
  if (k === "ranges" || k === "velocity_range" || k === "range") return `±${fmt(maxAbs(val), 3)}`;
  if (k === "params") return Object.entries(val).map(([a, b]) => `${a}=${Array.isArray(b) ? b.map((q) => fmt(q, 3)).join("〜") : fmt(b, 3)}`).join(", ");
  return Object.entries(raw).map(([a, b]) => `${a}=${typeof b === "number" ? fmt(b, 3) : JSON.stringify(b)}`).join(", ").slice(0, 60);
}

// ---------- slides ----------
function slideTitle(pres, d, D0) {
  const s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "表紙" });
  s.addText(d.title, { placeholder: "title" });
  s.addText(d.subtitle, { placeholder: "body" });
  const meta = `タスク: ${d.task}   |   run: ${d.run}   |   ${D0.num_envs} 並列環境 × ${D0.iterations} iter`;
  s.addText(meta, { x: MX, y: 6.4, w: W - 2 * MX, h: 0.4, fontSize: 12, color: "9AA7B5", isTextBox: true, margin: 0 });
}

function slideSummary(pres, C, d) {
  const s = content(pres, "要点", "概要");
  s.addText(d.message, { x: MX, y: CONTENT_Y, w: W - 2 * MX, h: 1.1, fontSize: 18, bold: true, color: HEX.text, isTextBox: true, margin: 0, valign: "top" });
  const n = d.stats.length, gap = 0.35, cw = (W - 2 * MX - gap * (n - 1)) / n;
  d.stats.forEach(([val, label], i) => {
    const x = MX + i * (cw + gap), y = 2.85;
    card(s, C, x, y, cw, 2.3, `stat${i}`);
    s.addText(val, { x: x + 0.3, y: y + 0.35, w: cw - 0.6, h: 1.0, fontSize: 40, bold: true, color: HEX.orange, isTextBox: true, margin: 0, fit: "shrink" });
    s.addText(label, { x: x + 0.3, y: y + 1.4, w: cw - 0.6, h: 0.7, fontSize: 14, color: HEX.text, isTextBox: true, margin: 0, valign: "top" });
  });
  s.addText("詳細は以降のスライド: モデル入出力 → シミュレーション条件 → 報酬 → ハイパーパラメータ → 学習経過 → 評価 → 推論動画",
    { x: MX, y: 5.6, w: W - 2 * MX, h: 0.5, fontSize: 12, color: HEX.muted, isTextBox: true, margin: 0 });
}

function slidePurpose(pres, C, d) {
  const s = content(pres, "目的と設定", "概要");
  const cw = (W - 2 * MX - 0.4) / 2, y = CONTENT_Y, h = 3.35;
  [["目的・背景", d.purpose], ["設定・変更点", d.changes]].forEach(([head, items], i) => {
    const x = MX + i * (cw + 0.4);
    card(s, C, x, y, cw, h, `card${i}`);
    s.addText(head, { x: x + 0.3, y: y + 0.25, w: cw - 0.6, h: 0.5, fontSize: 20, bold: true, color: i ? HEX.orange : HEX.teal, isTextBox: true, margin: 0 });
    bullets(s, items, { x: x + 0.3, y: y + 0.85, w: cw - 0.6, h: h - 1.0, margin: 0, fontSize: 13 });
  });
  lineage(s, d.id, 5.05);
}

// 7 実験の関係図（現在の exp を強調）
function lineage(s, cur, y0) {
  s.addText("実験の関係", { x: MX, y: y0, w: 3, h: 0.3, fontSize: 12, bold: true, color: HEX.muted, isTextBox: true, margin: 0 });
  const nodes = {
    exp001: [0, 0, "exp001 歩行"], exp004: [1, 0, "exp004 歩行+起き上がり"],
    exp002: [0, 1, "exp002 座る⇄立つ"], exp006: [1, 1, "exp006 +頭部ゼロ指令"], exp007: [2, 1, "exp007 +頭部衝撃ペナルティ"],
    exp003: [3, 0, "exp003 起き上がり"], exp005: [4, 0, "exp005 シード探索"],
  };
  const bw = 2.15, bh = 0.5, gx = 0.35, gy = 0.2, x0 = MX, yy = y0 + 0.4;
  const pos = (k) => { const [c, r] = nodes[k]; return [x0 + c * (bw + gx), yy + r * (bh + gy)]; };
  const arrow = (a, b, label) => { const [ax, ay] = pos(a), [bx, by] = pos(b);
    s.addShape("line", { x: ax + bw, y: ay + bh / 2, w: bx - ax - bw, h: 0, line: { color: HEX.gray, width: 1.25, endArrowType: "triangle" } }); };
  arrow("exp001", "exp004"); arrow("exp002", "exp006"); arrow("exp006", "exp007"); arrow("exp003", "exp005");
  for (const [k, [c, r, lab]] of Object.entries(nodes)) {
    const [x, y] = pos(k); const on = k === cur;
    s.addShape("roundRect", { x, y, w: bw, h: bh, rectRadius: 0.06, fill: { color: on ? HEX.orange : HEX.light }, line: { color: on ? HEX.orange : HEX.grid }, objectName: `lin_${k}` });
    s.addText(lab, { x, y, w: bw, h: bh, fontSize: 10.5, bold: on, color: on ? "FFFFFF" : HEX.text, align: "center", valign: "middle", isTextBox: true, margin: 0 });
  }
  const [x3] = pos("exp003");
  s.addText("exp003 / exp005 が起き上がりを学べなかったため、exp004 の教師には公式 alpha_stand を使用",
    { x: x3, y: yy + bh + gy, w: 2 * bw + gx, h: 0.5, fontSize: 10, color: HEX.muted, isTextBox: true, margin: 0, valign: "middle" });
}

function slideIO(pres, C, d, D0) {
  const s = content(pres, "モデルの入出力", "モデルと環境");
  const actor = D0.obs.actor, critic = D0.obs.critic;
  const rows = [["観測項（Actor）", "次元", "内容"]];
  actor.terms.forEach(([n, dim]) => rows.push([n, dim, OBS_DESC[n] || ""]));
  rows.push([{ text: "合計", options: { bold: true } }, { text: String(actor.total), options: { bold: true } }, "全タスク共通の 61 次元（方策を差し替え可能にするための規約）"]);
  table(s, rows, { x: MX, y: CONTENT_Y, w: 7.0, colW: [1.75, 0.6, 4.65], fontSize: 11 });
  const extra = critic.terms.filter(([n]) => !actor.terms.some(([m]) => m === n));
  s.addText(`Critic の入力: ${critic.total} 次元 = Actor の観測（ノイズなし）+ 特権情報 ` + extra.map(([n, k]) => `${n}(${k})`).join(", ") +
    "。学習時の価値推定のみに使い、実機では使わない（非対称 Actor-Critic）",
    { x: MX, y: 5.3, w: 7.0, h: 1.3, fontSize: 12, color: HEX.text, isTextBox: true, margin: 0, valign: "top" });
  // 右: ネットワーク図
  const bx = 8.1, bw = 4.6; let y = CONTENT_Y;
  const a = D0.agent;
  const boxes = [
    [`観測 ${actor.total}D（50 Hz）`, HEX.light, HEX.text],
    ["観測正規化（実行平均・分散）", HEX.light, HEX.text],
    [`MLP ${a.actor_hidden.join("-")}（${a.activation.toUpperCase()}）`, HEX.teal, "FFFFFF"],
    [`行動 平均 μ（${D0.action_dim}D）+ 共有 std σ`, HEX.orange, "FFFFFF"],
    ["関節目標角 = デフォルト姿勢 + a（PD 位置制御）", HEX.light, HEX.text],
  ];
  boxes.forEach(([t, fill, col], i) => {
    s.addShape("roundRect", { x: bx, y, w: bw, h: 0.62, rectRadius: 0.06, fill: { color: fill }, line: { color: fill }, objectName: `net${i}` });
    s.addText(t, { x: bx + 0.15, y, w: bw - 0.3, h: 0.62, fontSize: 12, bold: i === 2 || i === 3, color: col, align: "center", valign: "middle", isTextBox: true, margin: 0 });
    if (i < boxes.length - 1) s.addShape("line", { x: bx + bw / 2, y: y + 0.62, w: 0, h: 0.33, line: { color: HEX.gray, width: 1.5, endArrowType: "triangle" } });
    y += 0.95;
  });
  s.addText(`出力 ${D0.action_dim} 次元: 左脚 5（股 yaw/roll/pitch, 膝, 足首）+ 首・頭 4 + 右脚 5。学習時は N(μ, σ²) からサンプル、推論時は μ を使う`,
    { x: bx, y: y + 0.05, w: bw, h: 0.85, fontSize: 11, color: HEX.muted, isTextBox: true, margin: 0, valign: "top" });
}

function slideSim(pres, C, d, D0) {
  const s = content(pres, "シミュレーション（MuJoCo）の実行条件", "モデルと環境");
  const sm = D0.sim;
  const ctrlHz = Math.round(1 / (sm.timestep * sm.decimation));
  const rows = [["項目", "値"],
    ["シミュレータ", "MuJoCo Warp（mjlab 1.3.0）, GPU 並列"],
    ["物理刻み / 制御周期", `${sm.timestep * 1000} ms（${Math.round(1 / sm.timestep)} Hz） / ${ctrlHz} Hz（decimation ${sm.decimation}）`],
    ["エピソード長", `${sm.episode_length_s} 秒 = ${Math.round(sm.episode_length_s * ctrlHz)} 制御ステップ`],
    ["並列環境数", `${D0.num_envs}（環境間隔 ${sm.env_spacing} m, 互いに干渉しない）`],
    ["地形", sm.terrain === "plane" ? "平面" : sm.terrain],
    ["接触ソルバ反復", `${sm.iterations_solver}`],
    ["ロボット", "Microduck 14 関節。BAM アクチュエータモデル（XL330 の電流・摩擦・電圧降下）"],
    ["終了条件", D0.terminations.map((t) => TERM_DESC[t.name] || t.name).join(" / ")],
  ];
  table(s, rows, { x: MX, y: CONTENT_Y, w: 6.3, colW: [1.9, 4.4], fontSize: 11 });
  const er = [["ランダム化・外乱", "タイミング", "内容"]];
  D0.events.filter((e) => !["reset_robot_joints", "expand_bam_friction_fields", "reset_action_history"].includes(e.name)).forEach((e) => {
    const when = { startup: "起動時", reset: "リセット時", interval: e.interval_s ? `${e.interval_s[0]}〜${e.interval_s[1]} 秒ごと` : "一定間隔" }[e.mode] || e.mode;
    er.push([e.name, when, EVENT_DESC[e.name] || ""]);
  });
  table(s, er, { x: 7.15, y: CONTENT_Y, w: 5.6, colW: [1.95, 1.25, 2.4], fontSize: 10 });
}

function slideCommandsCurriculum(pres, C, d, D0) {
  const s = content(pres, D0.curriculum.length + 1 > 12 ? "指令（タスク入力）" : "指令（タスク入力）とカリキュラム", "モデルと環境");
  const cr = [["指令", "内容"]];
  for (const [n, c] of Object.entries(D0.commands)) {
    let desc = "";
    if (n === "twist" && c.sit_prob !== undefined) desc = `座る/立つフラグ（座る確率 ${c.sit_prob}）, ${c.resampling_time_range.join("〜")} 秒ごとに再抽選`;
    else if (n === "twist") desc = `vx ${c.ranges.lin_vel_x.join("〜")}, vy ${c.ranges.lin_vel_y.join("〜")} m/s, ωz ${c.ranges.ang_vel_z.join("〜")} rad/s。${c.resampling_time_range.join("〜")} 秒ごと`;
    else if (c.ranges) desc = `${Array.isArray(c.ranges) ? c.ranges.length : ""} 次元, 初期範囲 ±${fmt(Math.max(...c.ranges.flat().map(Math.abs)), 3)}（カリキュラムで拡大）, ${c.resampling_time_range.join("〜")} 秒ごと` + (c.zero_command_prob ? `, ゼロ指令 ${c.zero_command_prob * 100}%` : "");
    cr.push([n, desc]);
  }
  const cu = [["カリキュラム項目", "対象", "最初 → 最後", "最終段"]];
  D0.curriculum.forEach((c) => {
    const tgt = Object.values(c.target || {})[0] || "";
    cu.push([c.name, tgt, `${stageText(c.first_raw)} → ${stageText(c.last_raw)}`, c.last_iter ? `${c.last_iter} iter` : "-"]);
  });
  const note = "カリキュラム: 学習の進み（環境ステップ数）に応じて外乱・指令範囲・報酬の重みを段階的に変える。1 iter = 24 ステップ";
  const long = cu.length > 12 || cu.some((r) => String(r[2]).length > 60);
  if (!long) {
    table(s, cr, { x: MX, y: CONTENT_Y, w: 5.2, colW: [1.2, 4.0], fontSize: 10 });
    table(s, cu, { x: 6.1, y: CONTENT_Y, w: 6.65, colW: [1.9, 1.55, 2.4, 0.8], fontSize: 9.5 });
    s.addText(note, { x: MX, y: 6.45, w: 5.2, h: 0.45, fontSize: 10, color: HEX.muted, isTextBox: true, margin: 0 });
    return;
  }
  // 指令だけのスライドと、カリキュラム専用スライドに分ける
  table(s, cr, { x: MX, y: CONTENT_Y, w: W - 2 * MX, colW: [2.0, W - 2 * MX - 2.0], fontSize: 12 });
  bullets(s, ["指令は観測ベクトル 61D のうち 13D（command 3 + head_command 4 + body_command 6）として方策に入る。使わないスロットはゼロ埋め",
    "各指令は表の間隔で再抽選される。範囲はカリキュラムで段階的に広がる（次のスライド）",
    "実機では、この 13D をランタイムが外部の指示（コントローラ等）から書き込む"], { x: MX, y: 3.4, w: W - 2 * MX, h: 2.4, margin: 0, fontSize: 14 });
  s.addText(note, { x: MX, y: 6.3, w: W - 2 * MX, h: 0.45, fontSize: 11, color: HEX.muted, isTextBox: true, margin: 0 });
  const s2 = content(pres, "カリキュラム", "モデルと環境");
  const fs = cu.length > 16 ? 9 : 10;
  table(s2, cu.map((r, i) => (i ? [r[0], r[1], String(r[2]).replace(/(.{70})/g, "$1"), r[3]] : r)),
    { x: MX, y: CONTENT_Y, w: W - 2 * MX, colW: [2.6, 2.3, 6.4, 0.83], fontSize: fs, margin: [1, 4, 1, 4] });
}

function rewardRows(D0, cat) {
  const wmap = {};
  D0.curriculum.forEach((c) => { if (c.target && c.target.reward_name && "weight" in (c.last_raw || {})) wmap[c.target.reward_name] = c.last_raw.weight; });
  const rows = [];
  D0.rewards.forEach((r) => {
    const [c, desc] = REWARD_DESC[r.name] || [r.weight >= 0 ? "reward" : "penalty", r.func];
    if (c !== cat) return;
    const w0 = fmt(r.weight, 4), w1 = r.name in wmap ? fmt(wmap[r.name], 4) : null;
    rows.push([r.name, w1 !== null && w1 !== w0 ? `${w0} → ${w1}` : w0, desc]);
  });
  return rows;
}
function slideRewards(pres, C, d, D0) {
  const pos = rewardRows(D0, "reward"), neg = rewardRows(D0, "penalty");
  const intro = "報酬 = Σ 重み × 項（各制御ステップ, 時間刻みで正規化）。追従系は exp(−誤差²/σ²) 型。重みの「→」はカリキュラムによる変化。各項目の数式・意図・関数の形は巻末の付録で解説";
  const head = ["項目", "重み", "内容"];
  if (pos.length <= 13 && neg.length <= 13) {
    const s = content(pres, "報酬関数の概要", "報酬と学習設定");
    s.addText(intro, { x: MX, y: CONTENT_Y - 0.1, w: W - 2 * MX, h: 0.4, fontSize: 11, color: HEX.muted, isTextBox: true, margin: 0 });
    s.addText("目的（正の報酬）", { x: MX, y: 1.85, w: 6, h: 0.35, fontSize: 14, bold: true, color: HEX.teal, isTextBox: true, margin: 0 });
    s.addText("抑制（ペナルティ）", { x: 6.85, y: 1.85, w: 6, h: 0.35, fontSize: 14, bold: true, color: HEX.orange, isTextBox: true, margin: 0 });
    table(s, [head, ...pos], { x: MX, y: 2.25, w: 5.95, colW: [1.75, 0.95, 3.25], fontSize: 9.5 });
    table(s, [head, ...neg], { x: 6.85, y: 2.25, w: 5.9, colW: [1.75, 1.0, 3.15], fontSize: 9.5 });
  } else {
    [["目的（正の報酬）", pos, HEX.teal], ["抑制（ペナルティ）", neg, HEX.orange]].forEach(([lab, rows, col], i) => {
      const s = content(pres, `報酬関数の概要（${i + 1}/2）`, "報酬と学習設定");
      s.addText(intro, { x: MX, y: CONTENT_Y - 0.1, w: W - 2 * MX, h: 0.4, fontSize: 11, color: HEX.muted, isTextBox: true, margin: 0 });
      s.addText(lab, { x: MX, y: 1.85, w: 6, h: 0.35, fontSize: 14, bold: true, color: col, isTextBox: true, margin: 0 });
      table(s, [head, ...rows], { x: MX, y: 2.25, w: W - 2 * MX, colW: [2.4, 1.6, W - 2 * MX - 4.0], fontSize: rows.length > 15 ? 10 : 11, margin: [1, 5, 1, 5] });
    });
  }
}

function slideHyper(pres, C, d, D0) {
  const s = content(pres, "ハイパーパラメータ", "報酬と学習設定");
  const a = D0.agent;
  const rows = [["項目", "値"],
    ["アルゴリズム", a.algorithm.includes("ExpertBc") ? "PPO + 教師からの behavior cloning（PpoWithExpertBc）" : "PPO（rsl_rl）"],
    ["Actor / Critic", `MLP ${a.actor_hidden.join("-")} / ${a.critic_hidden.join("-")}, ${a.activation.toUpperCase()}, 観測正規化あり`],
    ["行動分布", `ガウス, 初期 std ${a.init_std}（全関節共通のスカラー）`],
    ["学習率", `${a.learning_rate}（KL 目標 ${a.desired_kl} で適応調整）`],
    ["γ / λ (GAE)", `${a.gamma} / ${a.lam}`],
    ["クリップ / エントロピー係数", `${a.clip_param} / ${a.entropy_coef}`],
    ["価値損失係数 / 勾配クリップ", `${a.value_loss_coef} / ${a.max_grad_norm}`],
    ["エポック × ミニバッチ", `${a.num_learning_epochs} × ${a.num_mini_batches}`],
    ["ロールアウト長", `${a.num_steps_per_env} step / env / iter`],
    ["seed / 保存間隔", `${a.seed} / ${a.save_interval} iter`],
  ];
  if (a.bc) rows.push(["蒸留（BC）", `係数 ${a.bc.coef}, lr ${a.bc.learning_rate}, 倒れ判定 > ${a.bc.gate_tilt_deg}° → stand expert, < ${a.bc.anchor_tilt_deg}° → 歩行 anchor`]);
  table(s, rows, { x: MX, y: CONTENT_Y, w: 7.4, colW: [2.3, 5.1], fontSize: 11 });
  const spi = D0.num_envs * a.num_steps_per_env, total = spi * D0.iterations;
  const stats = [[D0.num_envs.toLocaleString(), "並列環境数"], [spi.toLocaleString(), "サンプル / iter"],
    [`${(total / 1e6).toFixed(0)} M`, `総ステップ（${D0.iterations} iter）`], [D0.time_elapsed, `学習時間（RTX 3090, ${D0.iter_time_s_mean} s/iter）`]];
  stats.forEach(([val, lab], i) => {
    const x = 8.4 + (i % 2) * 2.25, y = CONTENT_Y + Math.floor(i / 2) * 2.0;
    card(s, C, x, y, 2.05, 1.8, `hs${i}`);
    s.addText(val, { x: x + 0.15, y: y + 0.25, w: 1.75, h: 0.7, fontSize: 22, bold: true, color: HEX.orange, isTextBox: true, margin: 0, fit: "shrink" });
    s.addText(lab, { x: x + 0.15, y: y + 1.0, w: 1.75, h: 0.7, fontSize: 11, color: HEX.text, isTextBox: true, margin: 0, valign: "top" });
  });
}

function slideCurves(pres, C, d, Ds) {
  const s = content(pres, "学習の経過", "学習経過");
  const cw = (W - 2 * MX - 0.4) / 2, ch = 2.55;
  const colors = [HEX.orange, HEX.teal, HEX.green];
  d.curves.forEach(([tag, label], i) => {
    const x = MX + (i % 2) * (cw + 0.4), y = CONTENT_Y + Math.floor(i / 2) * (ch + 0.2);
    const series = Ds.map((D0, k) => {
      const sr = D0.series[tag]; if (!sr) return null;
      return { name: Ds.length > 1 ? d.data[k].replace("exp005_", "seed ") : label, labels: sr.x.map(String), values: sr.y };
    }).filter(Boolean);
    if (!series.length) return;
    const n = series[0].labels.length;
    s.addChart("line", series, { x, y, w: cw, h: ch, ...chartBase(C), title: label, chartColors: colors.slice(0, series.length),
      lineSize: 1.75, lineDataSymbol: "none", showLegend: series.length > 1, legendPos: "b",
      catAxisLabelFrequency: Math.max(1, Math.round(n / 6)), catAxisTitle: "iteration", showCatAxisTitle: true, catAxisTitleFontSize: 9, catAxisTitleColor: HEX.muted,
      valAxisLabelFormatCode: "General", objectName: `curve${i}` });
  });
}

function slideImage(pres, C, title, section, imgPath, caption) {
  const s = content(pres, title, section);
  const { w: iw, h: ih } = imgSize(imgPath);
  const maxW = W - 2 * MX, maxH = 5.0;
  let w = maxW, h = (ih / iw) * w; if (h > maxH) { h = maxH; w = (iw / ih) * h; }
  s.addImage({ data: b64(imgPath), x: (W - w) / 2, y: CONTENT_Y, w, h, altText: caption });
  s.addText(caption, { x: MX, y: CONTENT_Y + h + 0.1, w: W - 2 * MX, h: 0.6, fontSize: 11, color: HEX.muted, isTextBox: true, margin: 0, valign: "top" });
}

function slideExtraImages(pres, C, d) {
  const e = d.extraImage; if (!e) return;
  const s = content(pres, e.title, "評価");
  const n = e.images.length; const gap = 0.15;
  let y = CONTENT_Y;
  const availH = (e.note ? 4.6 : 5.35) - gap * (n - 1);
  e.images.forEach(([cap, p]) => {
    const { w: iw, h: ih } = imgSize(p);
    let w = W - 2 * MX, h = (ih / iw) * w; const capH = 0.32;
    const hmax = availH / n - capH; if (h > hmax) { h = hmax; w = (iw / ih) * h; }
    s.addText(cap, { x: MX, y, w: W - 2 * MX, h: capH, fontSize: 12, bold: true, color: HEX.text, isTextBox: true, margin: 0 });
    s.addImage({ data: b64(p), x: MX, y: y + capH, w, h, altText: cap });
    y += capH + h + gap;
  });
  if (e.note) s.addText(e.note, { x: MX, y: y + 0.1, w: W - 2 * MX, h: 0.8, fontSize: 13, color: HEX.text, isTextBox: true, margin: 0, valign: "top" });
}

// ---------- evaluation slides ----------
function evalSlides(pres, C, d, Ds) {
  const k = d.evalKind;
  if (k === "exp001") {
    const s = content(pres, "評価: 学習の節目ごとの指標", "評価");
    const D0 = Ds[0]; const at = (tag, it) => { const sr = D0.series[tag]; let j = sr.x.findIndex((x) => x >= it); if (j < 0) j = sr.x.length - 1; return sr.y[j]; };
    const its = [0, 250, 500, 1000, 2000, 2999];
    const rows = [["iter", "平均報酬", "エピソード長", "並進誤差 [m/s]", "旋回誤差 [rad/s]", "方策 std"]];
    its.forEach((it) => rows.push([it, fmt(at("Train/mean_reward", it), 1), fmt(at("Train/mean_episode_length", it), 0),
      fmt(at("Metrics/twist/error_vel_xy", it), 2), fmt(at("Metrics/twist/error_vel_yaw", it), 2), fmt(at("Policy/mean_std", it), 2)]));
    table(s, rows, { x: MX, y: CONTENT_Y, w: 7.6, colW: [0.8, 1.2, 1.3, 1.5, 1.6, 1.2], fontSize: 12 });
    s.addText("値は各 iter 付近 25 iter の平均（学習ログから）。iter 0 の誤差が小さいのは、すぐ転倒してエピソードが短いため",
      { x: MX, y: 4.2, w: 7.6, h: 0.6, fontSize: 10, color: HEX.muted, isTextBox: true, margin: 0 });
    const f = EV.exp004_falls.exp001;
    card(s, C, 8.6, CONTENT_Y, 4.15, 2.3, "fallcard");
    s.addText(`${(f.ever_fallen_frac * 100).toFixed(1)}%`, { x: 8.85, y: CONTENT_Y + 0.3, w: 3.7, h: 0.9, fontSize: 40, bold: true, color: HEX.orange, isTextBox: true, margin: 0 });
    s.addText("20 秒間に転倒（傾き 60° 超）した個体の割合。512 体, 押し外乱あり（eval_falls.py）",
      { x: 8.85, y: CONTENT_Y + 1.25, w: 3.7, h: 0.9, fontSize: 12, color: HEX.text, isTextBox: true, margin: 0, valign: "top" });
    bullets(s, ["250 iter で歩行を獲得し、以降はカリキュラムの難化に追従しながら旋回・頭部姿勢の追従が改善",
      "並進速度の誤差は 2000 iter 以降 0.42 m/s で横ばい"], { x: 8.6, y: 4.1, w: 4.15, h: 2.5, margin: 0, fontSize: 13 });
    return;
  }
  if (k === "sitstand") {
    const s = content(pres, "評価: チェックポイント別の成功率（512 体）", "評価");
    const runs = d.sweepRuns, cks = ["1000", "1250", "1500", "1750", "2000", "2250", "2500", "2750", "2999"];
    const colors = { exp002: HEX.teal, exp006: HEX.orange, exp007: HEX.green };
    [["calm", "sit", "座る成功率: 外乱なし・頭部指令ゼロ（実機相当）"], ["final", "stand", "立つ成功率: 最終段の外乱あり"]].forEach(([cond, key, title], i) => {
      const data = runs.map((r) => ({ name: r, labels: cks, values: cks.map((c) => EV.sweep[r][c][cond][key]) }));
      s.addChart("line", data, { x: MX + i * 6.15, y: CONTENT_Y, w: 5.95, h: 3.6, ...chartBase(C), title, chartColors: runs.map((r) => colors[r]),
        lineSize: 2, lineDataSymbol: "circle", lineDataSymbolSize: 6, showLegend: true, legendPos: "b", valAxisMinVal: 0, valAxisMaxVal: 100,
        catAxisTitle: "checkpoint (iter)", showCatAxisTitle: true, catAxisTitleFontSize: 9, catAxisTitleColor: HEX.muted, objectName: `sweep${i}` });
    });
    const rows = [["判定（eval_sitstand.py）", "内容"],
      ["成功（座る）", "指令から 2.5 秒以上経過時点で 胴体高さ 0.060±0.015 m・傾き < 25°・頭部が床に触れていない"],
      ["成功（立つ）", "同 0.115±0.015 m・傾き < 20°"],
      ["条件", "外乱なし = カリキュラム最易段 + 頭部指令ゼロ固定 / 最終段の外乱 = 3000 iter 相当（押し ±0.3 m/s, 座位で後ろへ倒す外乱）"]];
    table(s, rows, { x: MX, y: 5.25, w: W - 2 * MX, colW: [2.4, W - 2 * MX - 2.4], fontSize: 10 });
    // 頭部接触
    const s2 = content(pres, "評価: 座るときに頭を床につくか", "評価");
    const hk = { exp002: [["exp002 model_2000", "exp002_m2000"]], exp006: [["exp002 model_2000", "exp002_m2000"], ["exp006 model_2999", "exp006_m2999"]],
      exp007: [["exp002 model_2000", "exp002_m2000"], ["exp006 model_2999", "exp006_m2999"], ["exp007 model_2500", "exp007_m2500"], ["exp007 model_2999", "exp007_m2999"]] }[d.id];
    const rows2 = [["方策", "頭が床に触れた個体", "座れ指令中の接触時間", "最大接触力"]];
    hk.forEach(([lab, key]) => { const h = EV.head[key]; rows2.push([lab, `${h.envs_with_head_floor_contact} / 32`, `${(h.head_contact_time_frac_while_sit_cmd * 100).toFixed(1)}%`, `${h.max_head_contact_normal_force_N.toFixed(0)} N`]); });
    table(s2, rows2, { x: MX, y: CONTENT_Y, w: 7.2, colW: [2.3, 1.8, 1.8, 1.3], fontSize: 12 });
    s2.addChart("bar", [{ name: "頭が床に触れた個体（/32）", labels: hk.map(([l]) => l.replace(" model_", "\nm")), values: hk.map(([, key]) => EV.head[key].envs_with_head_floor_contact) }],
      { x: 8.1, y: CONTENT_Y, w: 4.65, h: 3.6, ...chartBase(C), title: "頭が床に触れた個体（32 体中）", barDir: "col", chartColors: [HEX.orange],
        showLegend: false, showValue: true, dataLabelPosition: "outEnd", dataLabelColor: HEX.text, dataLabelFontSize: 10, dataLabelFontFace: "+mn-lt", valAxisMinVal: 0, valAxisMaxVal: 32, objectName: "headbar" });
    bullets(s2, ["計測: 立つ 2 秒 → 座る 4 秒 × 10 周の時間割, 32 体, 外乱なし・頭部指令ゼロ（head_contact_probe.py）",
      "MuJoCo の衝突判定で頭部サブツリー（neck_pitch 以下）と床（terrain）の接触・法線力を検出",
      "参考: 公式 VelStand は頭部の床反力 15 N 超を危険とみなす（顔からの転倒は約 60 N）"], { x: MX, y: CONTENT_Y + 0.5 + 0.42 * hk.length + 0.35, w: 7.2, h: 2.2, margin: 0, fontSize: 12 });
    if (d.id === "exp002") {
      const s3 = content(pres, "評価: 失敗原因の切り分け（model_2250）", "評価");
      const A = EV.exp002_ablation;
      const rows3 = [["条件", "座る", "立つ"],
        ["最易段（外乱なし・頭部指令の範囲も最小）", "67%", "99%"],
        ["最易段 ＋ 頭部指令の範囲だけ最終段", `${A.easy_but_head_pose_range_last.sit}%`, `${A.easy_but_head_pose_range_last.stand}%`],
        ["最易段 ＋ 押し外乱だけ最終段", `${A.easy_but_push_magnitude_last.sit}%`, `${A.easy_but_push_magnitude_last.stand}%`],
        ["最易段 ＋ 重心 / 頭部重心 / 頭の急変 / 後ろへの外乱 のどれか", "65〜71%", "99〜100%"],
        ["最終段 ＋ 押し外乱だけなし", `${A.final_but_push_magnitude_first.sit}%`, `${A.final_but_push_magnitude_first.stand}%`],
        ["最終段 ＋ 頭部指令の範囲だけ最小", `${A.final_but_head_pose_range_first.sit}%`, `${A.final_but_head_pose_range_first.stand}%`]];
      table(s3, rows3, { x: MX, y: CONTENT_Y, w: 8.0, colW: [5.6, 1.2, 1.2], fontSize: 12 });
      const labs = ["最易段", "+頭部指令範囲", "+押し外乱", "最終段−押し", "最終段−頭部指令範囲"];
      const keys = [null, "easy_but_head_pose_range_last", "easy_but_push_magnitude_last", "final_but_push_magnitude_first", "final_but_head_pose_range_first"];
      const val = (k, f, base) => (k ? A[k][f] : base);
      s3.addChart("bar", [{ name: "座る", labels: labs, values: keys.map((k) => val(k, "sit", 67)) }, { name: "立つ", labels: labs, values: keys.map((k) => val(k, "stand", 99)) }],
        { x: MX, y: 4.05, w: 8.0, h: 2.75, ...chartBase(C), title: "成功率 [%]", barDir: "col", chartColors: [HEX.teal, HEX.orange], showLegend: true, legendPos: "r",
          valAxisMinVal: 0, valAxisMaxVal: 100, showValue: true, dataLabelPosition: "outEnd", dataLabelColor: HEX.text, dataLabelFontSize: 9, dataLabelFontFace: "+mn-lt", dataLabelFormatCode: "0", objectName: "ablbar" });
      bullets(s3, ["外乱・指令に関わるカリキュラム 6 項目を 1 つずつ入れ替えて評価（eval_sitstand.py --pin）",
        "「座らない」の主因は頭部指令がほぼゼロであること（頭部指令が動けば 91% 座る）",
        "「立てずに後ろに傾いたまま」の主因は押し外乱（押しをなくすと立つ 97%）",
        "→ exp006 / exp007 の対策につながった"], { x: 8.9, y: CONTENT_Y, w: 3.85, h: 5.0, margin: 0, fontSize: 13 });
    }
    return;
  }
  if (k === "exp003" || k === "exp005") {
    const s = content(pres, "評価: 初期姿勢別の起き上がり成功率", "評価");
    const src = k === "exp003" ? Object.entries(EV.exp003).map(([ck, g]) => [`model_${ck}`, g]) : Object.entries(EV.exp005).map(([sd, g]) => [`seed ${sd.slice(1)}（model_999）`, g]);
    const groups = [["upright", "座位など"], ["face_down", "うつ伏せ"], ["face_up", "仰向け"], ["side", "横向き"]];
    const rows = [["方策", ...groups.map(([, l]) => l)]];
    src.forEach(([lab, g]) => rows.push([lab, ...groups.map(([key]) => g[key] ? `${(g[key].ever_stood * 100).toFixed(1)}%（n=${g[key].n}）` : "-")]));
    const as = EV.alpha_stand;
    rows.push([{ text: "参考: 公式 alpha_stand", options: { italic: true } }, ...groups.map(([key]) => ({ text: `${(as[key].ever_stood * 100).toFixed(0)}%`, options: { italic: true } }))]);
    table(s, rows, { x: MX, y: CONTENT_Y, w: W - 2 * MX, colW: [3.0, 2.3, 2.3, 2.2, 2.33], fontSize: 12 });
    const last = src[src.length - 1];
    s.addChart("bar", [{ name: last[0], labels: groups.map(([, l]) => l), values: groups.map(([key]) => +(last[1][key].ever_stood * 100).toFixed(1)) },
      { name: "公式 alpha_stand", labels: groups.map(([, l]) => l), values: groups.map(([key]) => +(as[key].ever_stood * 100).toFixed(1)) }],
      { x: MX, y: 3.65, w: 6.3, h: 3.15, ...chartBase(C), title: "6 秒以内に一度でも立てた割合 [%]", barDir: "col", chartColors: [HEX.orange, HEX.gray],
        showLegend: true, legendPos: "b", valAxisMinVal: 0, valAxisMaxVal: 100, showValue: true, dataLabelPosition: "outEnd", dataLabelColor: HEX.text, dataLabelFontSize: 9, dataLabelFontFace: "+mn-lt", dataLabelFormatCode: "0.0", objectName: "standbar" });
    bullets(s, [`評価: ${k === "exp005" ? "各シード 2048 体" : "2048 体"}を学習最終段の初期姿勢分布で開始。1 エピソード（6 秒）中に 傾き < 20° かつ 胴体高さ > 0.10 m に一度でも到達した割合（eval_standup.py）`,
      "初期姿勢は自動リセット直後の重力方向で分類", "同じ評価で公式 alpha_stand は全姿勢 100%（評価方法が成功を検出できることの確認）"],
      { x: 7.2, y: 3.75, w: 5.55, h: 3.0, margin: 0, fontSize: 12 });
    return;
  }
  if (k === "exp004") {
    const s = content(pres, "評価: 寝た姿勢からの起き上がりと歩行中の転倒", "評価");
    const groups = [["face_down", "うつ伏せ"], ["face_up", "仰向け"], ["side", "横向き"]];
    const rows = [["方策", ...groups.map(([, l]) => l)]];
    Object.entries(EV.exp004_rec).forEach(([ck, g]) => rows.push([`model_${ck}`, ...groups.map(([key]) => `${(g[key].ever_stood * 100).toFixed(0)}% / ${(g[key].success_at_end * 100).toFixed(0)}% / ${g[key].median_time_to_stand_s.toFixed(2)} s`)]));
    table(s, rows, { x: MX, y: CONTENT_Y, w: 7.6, colW: [1.6, 2.0, 2.0, 2.0], fontSize: 11 });
    s.addText("各セル: 一度でも立てた割合 / 20 秒後に立っている割合 / 立つまでの中央値。512 体を全員寝た姿勢から開始（eval_standup.py --all-prone, 学習最終段の外乱あり）",
      { x: MX, y: 3.0, w: 7.6, h: 0.7, fontSize: 10, color: HEX.muted, isTextBox: true, margin: 0 });
    const F = EV.exp004_falls;
    s.addChart("bar", [{ name: "20 秒間に転倒した割合 [%]", labels: ["exp001（歩行専用）", "exp004（VelStand）"], values: [+(F.exp001.ever_fallen_frac * 100).toFixed(1), +(F.exp004.ever_fallen_frac * 100).toFixed(1)] }],
      { x: 8.5, y: CONTENT_Y, w: 4.25, h: 3.4, ...chartBase(C), title: "歩行中の転倒（傾き 60° 超, 512 体）", barDir: "col", chartColors: [HEX.orange],
        showLegend: false, showValue: true, dataLabelPosition: "outEnd", dataLabelColor: HEX.text, dataLabelFontSize: 10, dataLabelFontFace: "+mn-lt", dataLabelFormatCode: "0.0", valAxisMinVal: 0, objectName: "fallbar" });
    bullets(s, ["寝た姿勢から 98〜100% が中央値 0.3〜0.8 秒で起き上がる（自前 StandUp の 0% から大きく前進）",
      "20 秒後に立っている割合が低めなのは、評価中も転倒させる押しが入り続けるため",
      "歩行中の転倒は歩行専用モデルの約 3 倍。転んでも起き上がれる前提の方策になっている"], { x: MX, y: 3.95, w: 7.6, h: 2.8, margin: 0, fontSize: 13 });
    s.addText("eval_falls.py, 押し外乱あり（歩行タスクの押しはカリキュラムに依存しない）", { x: 8.5, y: 4.95, w: 4.25, h: 0.6, fontSize: 10, color: HEX.muted, isTextBox: true, margin: 0 });
  }
}

function slideVideo(pres, C, d, vdef) {
  const s = content(pres, `推論動画: ${vdef.title}`, "推論動画");
  const poster = path.join(HERE, "posters", vdef.poster + ".png");
  const maxW = 8.3, maxH = 5.05; let w = maxW, h = (vdef.h / vdef.w) * w; if (h > maxH) { h = maxH; w = (vdef.w / vdef.h) * h; }
  s.addMedia({ type: "video", path: vdef.path, x: MX, y: CONTENT_Y, w, h, cover: b64(poster), objectName: "video" });
  const tx = MX + w + 0.4, tw = W - MX - tx;
  card(s, C, tx, CONTENT_Y, tw, h, "vcard");
  s.addText("条件と見どころ", { x: tx + 0.25, y: CONTENT_Y + 0.25, w: tw - 0.5, h: 0.45, fontSize: 16, bold: true, color: HEX.teal, isTextBox: true, margin: 0 });
  s.addText(vdef.caption, { x: tx + 0.25, y: CONTENT_Y + 0.85, w: tw - 0.5, h: h - 1.9, fontSize: 13, color: HEX.text, isTextBox: true, margin: 0, valign: "top" });
  s.addText("スライドショーで再生。推論時は方策の平均 μ（決定的な行動）を使用。\nファイル: " + path.relative("/home/motono0223/workbook-microduck", vdef.path),
    { x: tx + 0.25, y: CONTENT_Y + h - 1.15, w: tw - 0.5, h: 1.0, fontSize: 9, color: HEX.muted, isTextBox: true, margin: 0, valign: "bottom" });
}

function slideClosing(pres, C, d) {
  const s = pres.addSlide({ masterName: "CLOSING_DARK", sectionTitle: "まとめ" });
  s.addText("まとめと次の一手", { placeholder: "title" });
  s.addText("結論", { x: MX, y: 1.45, w: 7.3, h: 0.45, fontSize: 18, bold: true, color: "F2A07A", isTextBox: true, margin: 0 });
  s.addText(d.conclusions.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < d.conclusions.length - 1 } })),
    { x: MX, y: 2.0, w: 7.3, h: 4.6, fontSize: 15, color: "FFFFFF", isTextBox: true, margin: 0, valign: "top", paraSpaceAfter: 8 });
  s.addShape("roundRect", { x: 8.3, y: 1.45, w: 4.43, h: 5.15, rectRadius: 0.08, fill: { color: "33404F" }, line: { color: "33404F" }, objectName: "nextcard" });
  s.addText("次の一手", { x: 8.55, y: 1.65, w: 4.0, h: 0.45, fontSize: 18, bold: true, color: "F2A07A", isTextBox: true, margin: 0 });
  s.addText(d.next.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < d.next.length - 1 } })),
    { x: 8.55, y: 2.2, w: 4.0, h: 4.2, fontSize: 14, color: "FFFFFF", isTextBox: true, margin: 0, valign: "top", paraSpaceAfter: 8 });
}

// ---------- 付録: 報酬関数の解説 ----------
const RX_PATH = path.join(HERE, "reward_explain.json");
const RX = fs.existsSync(RX_PATH) ? JSON.parse(fs.readFileSync(RX_PATH, "utf8")) : {};

function weightText(D0, name) {
  const r = D0.rewards.find((x) => x.name === name);
  let w1 = null;
  D0.curriculum.forEach((c) => { if (c.target && c.target.reward_name === name && "weight" in (c.last_raw || {})) w1 = c.last_raw.weight; });
  const w0 = fmt(r.weight, 4);
  return w1 !== null && fmt(w1, 4) !== w0 ? `${w0} → ${fmt(w1, 4)}（カリキュラム）` : w0;
}

function slideRewardGuide(pres, C, d) {
  const s = content(pres, "付録: 報酬関数の読み方", "付録: 報酬関数の解説");
  card(s, C, MX, CONTENT_Y, 6.6, 1.35, "guide_formula");
  s.addText([{ text: "1 制御ステップ（0.02 秒）の報酬\n", options: { fontSize: 12, color: HEX.muted, breakLine: true } },
    { text: "r_t = Σ_i  w_i × term_i(s_t, a_t) × dt", options: { fontSize: 20, bold: true, color: HEX.text } }],
  { x: MX + 0.25, y: CONTENT_Y + 0.15, w: 6.1, h: 1.05, isTextBox: true, margin: 0, valign: "middle" });
  const rows = [["関数の返す値", "重み", "意味"],
    ["報酬（≥ 0）", "正", "望ましい状態ほど大きい（目的）"],
    ["コスト（≥ 0）", "負", "望ましくない量ほど大きい → 負の重みで罰する"],
    ["自己符号反転（≤ 0）", "正", "関数が自分で負値を返す → 正の重みで罰になる"]];
  table(s, rows, { x: MX, y: 3.05, w: 6.6, colW: [2.0, 0.7, 3.9], fontSize: 12 });
  bullets(s, ["各項目のスライドの右のグラフは「重みを掛ける前の項の値」を 1 つの変数に対して描いたもの",
    "追従系の多くはガウス型 exp(−誤差²/σ²): 誤差 0 で 1、σ で約 0.37。σ が小さいほど「ほぼ完璧」でないと報酬が出ない",
    "ゲート（条件）付きの項や複数の量の積は 1 次元の曲線で描けないため、条件を文章で示す",
    "重みの「→」はカリキュラムで学習中に変わることを示す（例: 動作を覚えた後にペナルティを強める）"],
    { x: MX, y: 4.85, w: 6.6, h: 2.0, margin: 0, fontSize: 12 });
  const xs = [...Array(26).keys()].map((i) => +(i * 0.08).toFixed(2));
  const sig = [0.2, 0.5, 1.0];
  s.addChart("line", sig.map((sg) => ({ name: `σ = ${sg}`, labels: xs.map(String), values: xs.map((x) => +Math.exp(-(x * x) / (sg * sg)).toFixed(4)) })),
    { x: 7.55, y: CONTENT_Y, w: 5.2, h: 3.6, ...chartBase(C), title: "ガウス型の報酬 exp(−誤差²/σ²)", chartColors: [HEX.orange, HEX.teal, HEX.green],
      lineSize: 2, lineDataSymbol: "none", showLegend: true, legendPos: "b", valAxisMinVal: 0, valAxisMaxVal: 1,
      catAxisLabelFrequency: 5, catAxisTitle: "誤差", showCatAxisTitle: true, catAxisTitleFontSize: 9, catAxisTitleColor: HEX.muted, objectName: "gauss_guide" });
  s.addText("この付録の数式・条件は実装コード（mjlab / mjlab_microduck の mdp）から読み取ったもの。パラメータはこの run の設定値",
    { x: 7.55, y: 5.25, w: 5.2, h: 0.8, fontSize: 11, color: HEX.muted, isTextBox: true, margin: 0, valign: "top" });
}

function rewardTermBlock(s, C, D0, name, y, idx) {
  const e = RX[name]; const [cat] = REWARD_DESC[name] || ["reward"];
  const isPen = cat === "penalty";
  const rowH = 2.62, lw = 7.75;
  card(s, C, MX, y, W - 2 * MX, rowH, `rt_card${idx}`);
  // 見出し
  s.addText(name, { x: MX + 0.25, y: y + 0.12, w: 4.2, h: 0.4, fontSize: 16, bold: true, color: HEX.text, isTextBox: true, margin: 0 });
  s.addShape("roundRect", { x: MX + 4.5, y: y + 0.17, w: 1.1, h: 0.3, rectRadius: 0.1, fill: { color: isPen ? HEX.orange : HEX.teal }, line: { color: isPen ? HEX.orange : HEX.teal }, objectName: `rt_tag${idx}` });
  s.addText(isPen ? "ペナルティ" : "報酬", { x: MX + 4.5, y: y + 0.17, w: 1.1, h: 0.3, fontSize: 10, bold: true, color: "FFFFFF", align: "center", valign: "middle", isTextBox: true, margin: 0 });
  s.addText(`重み ${weightText(D0, name)}`, { x: MX + 5.75, y: y + 0.12, w: 2.3, h: 0.4, fontSize: 11, color: HEX.muted, isTextBox: true, margin: 0, valign: "middle", fit: "shrink" });
  if (!e) {
    s.addText("（解説データなし）", { x: MX + 0.25, y: y + 0.6, w: lw, h: 0.4, fontSize: 12, color: HEX.muted, isTextBox: true, margin: 0 });
    return;
  }
  // 数式
  s.addShape("rect", { x: MX + 0.25, y: y + 0.58, w: lw - 0.1, h: 0.5, fill: { color: "FFFFFF" }, line: { color: HEX.grid }, objectName: `rt_formula${idx}` });
  s.addText(e.formula, { x: MX + 0.35, y: y + 0.58, w: lw - 0.3, h: 0.5, fontSize: 11, color: HEX.text, isTextBox: true, margin: 0, valign: "middle", fit: "shrink" });
  const lines = [["記号", e.symbols], ["何を測る", e.what], ["なぜ必要", e.why]];
  if (e.gate) lines.push(["有効条件", e.gate]);
  s.addText(lines.flatMap(([k, v], i) => [{ text: `${k}  `, options: { bold: true, color: isPen ? HEX.orange : HEX.teal } },
    { text: v, options: { color: HEX.text, breakLine: i < lines.length - 1 } }]),
  { x: MX + 0.25, y: y + 1.15, w: lw - 0.1, h: rowH - 1.25, fontSize: 10, isTextBox: true, margin: 0, valign: "top", paraSpaceAfter: 2, fit: "shrink" });
  // 右: 関数の形
  const cx = MX + lw + 0.3, cw = W - MX - cx - 0.15;
  const curve = (e.shape && e.shape.curve) || [];
  if (curve.length >= 3) {
    s.addChart("line", [{ name, labels: curve.map(([x]) => String(+(+x).toPrecision(3))), values: curve.map(([, yy]) => +(+yy).toPrecision(4)) }],
      { x: cx, y: y + 0.1, w: cw, h: rowH - 0.2, ...chartBase(C), title: "項の値（重み掛け前）", titleFontSize: 10, chartColors: [isPen ? HEX.orange : HEX.teal],
        lineSize: 2, lineDataSymbol: "none", showLegend: false, catAxisLabelFrequency: Math.max(1, Math.round(curve.length / 5)),
        catAxisTitle: e.shape.x || "", showCatAxisTitle: true, catAxisTitleFontSize: 9, catAxisTitleColor: HEX.muted, objectName: `rt_chart${idx}` });
  } else {
    const note = (e.shape && e.shape.params && e.shape.params.note) || "条件付き・複数量の項のため 1 次元の曲線では表せない";
    s.addShape("rect", { x: cx, y: y + 0.25, w: cw, h: rowH - 0.5, fill: { color: "FFFFFF" }, line: { color: HEX.grid, dashType: "dash" }, objectName: `rt_nochart${idx}` });
    s.addText(note, { x: cx + 0.15, y: y + 0.3, w: cw - 0.3, h: rowH - 0.6, fontSize: 10, color: HEX.muted, isTextBox: true, margin: 0, valign: "middle", fit: "shrink" });
  }
}

function slideRewardTerms(pres, C, d, D0) {
  const order = [...rewardRows(D0, "reward"), ...rewardRows(D0, "penalty")].map((r) => r[0]);
  for (let i = 0; i < order.length; i += 2) {
    const pair = order.slice(i, i + 2);
    const s = content(pres, `付録: 報酬項の解説（${Math.floor(i / 2) + 1}/${Math.ceil(order.length / 2)}）`, "付録: 報酬関数の解説");
    pair.forEach((name, k) => rewardTermBlock(s, C, D0, name, CONTENT_Y + k * 2.78, i + k));
  }
}

async function buildDeck(d, outDir) {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  pres.title = d.title; pres.author = "Microduck RL workbook"; pres.subject = d.subtitle;
  const C = pres.SchemeColor;
  defineLayouts(pres, C, d.id);
  const Ds = d.data.map(DATA), D0 = Ds[0];
  for (const sec of ["表紙", "概要", "モデルと環境", "報酬と学習設定", "学習経過", "評価", "推論動画", "まとめ"]) { /* sections are added lazily */ }
  const addSec = (t) => pres.addSection({ title: t });
  addSec("表紙"); slideTitle(pres, d, D0);
  addSec("概要"); slideSummary(pres, C, d); slidePurpose(pres, C, d);
  addSec("モデルと環境"); slideIO(pres, C, d, D0); slideSim(pres, C, d, D0); slideCommandsCurriculum(pres, C, d, D0);
  addSec("報酬と学習設定"); slideRewards(pres, C, d, D0); slideHyper(pres, C, d, D0);
  addSec("学習経過"); slideCurves(pres, C, d, Ds);
  slideImage(pres, C, "学習の経過: 報酬項ごとの内訳", "学習経過", path.join(d.runDir, "plots/02_reward_terms.png"),
    "各報酬項の 1 エピソードあたりの値（重み込み）。細線 = 生値, 太線 = 指数移動平均。青 = 報酬, 橙 = ペナルティ。カリキュラムで重みが変わる項は段状に変化する");
  addSec("評価"); evalSlides(pres, C, d, Ds); slideExtraImages(pres, C, d);
  addSec("推論動画"); d.videos.forEach((vd) => slideVideo(pres, C, d, vd));
  addSec("まとめ"); slideClosing(pres, C, d);
  addSec("付録: 報酬関数の解説"); slideRewardGuide(pres, C, d); slideRewardTerms(pres, C, d, D0);
  const out = path.join(outDir, `${d.id}.pptx`);
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("wrote", out);
}

(async () => {
  const outDir = process.argv[2]; const only = process.argv.slice(3);
  fs.mkdirSync(outDir, { recursive: true });
  for (const d of DECKS) if (!only.length || only.includes(d.id)) await buildDeck(d, outDir);
})();
