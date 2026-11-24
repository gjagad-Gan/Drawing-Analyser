"""Step 8b - PDF drawing set from the JSON / PNG outputs.

python3 report_drawings.py job.json
Sheets: 1 plan on parting (castings, necks, risers, stepped runners, wells, sprue/filter, dimensions, weights)
        2 part analysis + feeding simulation   3 temperature map + pouring window + shell table   4 cope sections (if built)
"""
import sys, os, json, math, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon
from matplotlib.backends.backend_pdf import PdfPages
import castlib as C

cfg = C.load_config(sys.argv[1]); lay = C.read_json(cfg, "layout.json"); fd = cfg["feeding"]
def opt(n):
    p = C.out_path(cfg, n); return json.load(open(p)) if os.path.exists(p) else None
fs, pw, sh, tl = opt("feeder_sim.json"), opt("pour_window.json"), opt("shell.json"), opt("temp_loss.json")
INK, CAST, GATE, RUN, RIS = "#1b1b1b", "#9aa7b4", "#d9822b", "#c0392b", "#8e1b10"
PX, PY = cfg.get("plate", {}).get("x", 750.0), cfg.get("plate", {}).get("y", 650.0); M = cfg.get("plate", {}).get("margin", 30.0)
SIL = C.silhouette(cfg); YR = lay["yr"]; R = lay["riser"]["D"] / 2
def tb(fig, k, n, t):
    fig.text(0.99, 0.012, f"{cfg.get('job', '')} — gating layout | {t} | sheet {k}/{n} | nominal size: apply pattern shrink | confirm by sectioned / X-ray first-off",
             ha="right", va="bottom", fontsize=7.5, bbox=dict(fc="white", ec=INK, lw=0.8))
def place(p, xo, yo, rot): return (-p if rot else p) + [xo, yo]
nsheets = 4 if os.path.exists(C.out_path(cfg, "cope_shell.stl")) else 3
pdf = PdfPages(C.out_path(cfg, "gating_layout.pdf"))
# ---------------- 1 plan ----------------
fig, ax = plt.subplots(figsize=(16.5, 11.7))
ax.add_patch(Rectangle((-PX / 2, -PY / 2), PX, PY, fc="#f6f4ef", ec=INK, lw=1.4))
ax.add_patch(Rectangle((-PX / 2 + M, -PY / 2 + M), PX - 2 * M, PY - 2 * M, fc="none", ec="#888", lw=0.6, ls="--"))
ymax = max(lay["rows_y"]) + 25
for s in (1, -1):
    ax.add_patch(Rectangle((-lay["cross"]["root_d"] / 2, min(s * 33, s * ymax)), lay["cross"]["root_d"], ymax - 33, fc=RUN, alpha=.8, ec="none"))
for yc in lay["rows_y"]:
    for s in (1, -1):
        xs = sorted([abs(r[0]) for r in lay["risers"] if abs(r[1] - yc) < 0.1 and math.copysign(1, r[0]) == s]); x0 = 33.0 if abs(yc) < 45 else 0.0
        pts = [x0] + xs
        for i in range(len(xs)):
            w = max(lay["branch"]["min_d"], lay["branch"]["root_d"] * math.sqrt((len(xs) - i) / len(xs)))
            a, b = sorted([s * pts[i], s * pts[i + 1]]); ax.add_patch(Rectangle((a, yc - w / 2), b - a, w, fc=RUN, alpha=.85, ec="none"))
        a, b = sorted([s * xs[-1], s * lay["run_end"]]); ax.add_patch(Rectangle((a, yc - 5), b - a, 10, fc=RUN, alpha=.85, ec="none"))
for i, (xo, yo, rot) in enumerate(lay["casts"]):
    for c in SIL: ax.add_patch(Polygon(place(c, xo, yo, rot), closed=True, fc=CAST, ec=INK, lw=0.4))
    sg = -1 if rot else 1
    for n in fd["necks"]:
        xc = xo + (n["x"] if not rot else -n["x"]); y0 = yo + sg * n["face_y"]; y1 = yo + sg * (YR - R + 1)
        ax.add_patch(Rectangle((xc - n["w"] / 2, min(y0, y1)), n["w"], abs(y1 - y0), fc=GATE, ec=INK, lw=0.3))
for x, y in lay["risers"]: ax.add_patch(Circle((x, y), R, fc=RIS, ec=INK, lw=0.4, zorder=3))
ax.add_patch(Rectangle((-25, -25), 50, 50, fc="#f0e2a8", ec=INK, hatch="xx", zorder=4)); ax.add_patch(Circle((0, 0), lay["choke_dia_mm"] / 2, fc="#555", zorder=5))
ax.set_xlim(-PX / 2 - 40, PX / 2 + 40); ax.set_ylim(-PY / 2 - 40, PY / 2 + 30); ax.set_aspect("equal"); ax.axis("off")
ax.set_title(f"PLAN ON PARTING (Z=0) — {lay['cavities']} cavities, {len(lay['risers'])} blind risers Ø{lay['riser']['D']:.0f} (Z {lay['riser']['z0']}…{lay['riser']['z1']}), "
             f"stepped runners Ø{lay['branch']['root_d']:.0f}→Ø{lay['branch']['min_d']:.0f}, cross Ø{lay['cross']['root_d']:.0f}→Ø{lay['cross']['tip_d']:.0f}\n"
             f"Poured {lay['poured_kg']:.1f} kg | castings {lay['castings_total_kg']:.1f} kg | yield {lay['yield_pct']:.1f} % | fill {lay['fill_time_s']} s, choke Ø{lay['choke_dia_mm']:.1f}, sprue top Ø{lay['sprue_top_dia_mm']:.1f}",
             fontsize=10, loc="left")
tb(fig, 1, nsheets, "plan"); pdf.savefig(fig); plt.close(fig)
# ---------------- 2 analysis + sim ----------------
fig = plt.figure(figsize=(16.5, 11.7))
for k, (img, rect) in enumerate((("hot_spots.png", [0.02, 0.62, 0.62, 0.33]), ("profiles.png", [0.02, 0.36, 0.62, 0.25]), ("feeder_sim.png", [0.02, 0.04, 0.62, 0.32]), ("core_need.png", [0.66, 0.70, 0.32, 0.25]))):
    p = C.out_path(cfg, img)
    if os.path.exists(p): a = fig.add_axes(rect); a.imshow(plt.imread(p)); a.axis("off")
a = fig.add_axes([0.66, 0.08, 0.32, 0.58]); a.axis("off")
txt = ["FEEDING SIMULATION (worst arm)"]
if fs:
    for c in fs["cases"]: txt.append(f"in-mould {c['T_cast']:.0f}, runner {c['T_gate']:.0f}: unfed {c['unfed_mm3']:.0f} mm³, neck/arm {c['neck_vs_arm']:.2f}, riser/neck {c['riser_vs_neck']:.2f}")
    txt.append("criteria: unfed 0, neck/arm ≥ 1.10, riser/neck ≥ 1.30  →  " + ("PASS" if fs.get("pass") else "FAIL"))
txt += ["", "NECKS"] + [f"X {n['x']}: {n['w']} × {n['t']} on face Y {n['face_y']}" for n in fd["necks"]]
txt += ["", f"Riser Ø{lay['riser']['D']:.0f}, Z {lay['riser']['z0']} … {lay['riser']['z1']}, {lay['riser_vol_cm3']:.1f} cm³ each", f"Clearances: " + ", ".join(f"{k} {v:.1f}" for k, v in lay["clearances_mm"].items())]
a.text(0, 1, "\n".join(txt), va="top", fontsize=8.5, family="monospace", wrap=True)
tb(fig, 2, nsheets, "part analysis and feeding simulation"); pdf.savefig(fig); plt.close(fig)
# ---------------- 3 temperature / window / shell ----------------
fig = plt.figure(figsize=(16.5, 11.7))
p = C.out_path(cfg, "temp_map.png")
if os.path.exists(p): a = fig.add_axes([0.01, 0.50, 0.98, 0.46]); a.imshow(plt.imread(p)); a.axis("off")
a = fig.add_axes([0.03, 0.06, 0.45, 0.40]); a.axis("off")
if pw:
    rows = [["Cup °C", "Hottest", "Farthest 5 s", "Farthest 2 s", "Riser eff.", "Verdict"]] + [[x["cup"], x["near"], x["far_5s"], x["far_2s"], x["riser_eff_needed"], x["verdict"]] for x in pw["rows"] if x["cup"] % 10 == 0]
    t = a.table(cellText=rows, loc="upper left", cellLoc="left"); t.auto_set_font_size(False); t.set_fontsize(8); t.scale(1, 1.35)
    if pw["window"]["first_mould_max"]: a.set_title(f"POURING WINDOW (stream / cup): first mould ≤ {pw['window']['first_mould_max']} °C, last mould ≥ {pw['window']['last_mould_min']} °C", loc="left", fontsize=10)
a = fig.add_axes([0.52, 0.06, 0.46, 0.40]); a.axis("off")
if sh:
    rows = [["t mm", "Cope kg", "Handling sag", "Edges-only bow", "SF edges-only", "Hold-down kgf"]] + [[x["t"], f"{x['cope_kg']:.1f}", f"{x['sag_handling_mm']:.2f}", f"{x['bow_edges_only_mm']:.1f}", f"{x['SF_edges_only']:.1f}", f"{x['hold_down_kgf']:.0f}"] for x in sh["rows"]]
    t = a.table(cellText=rows, loc="upper left", cellLoc="left"); t.auto_set_font_size(False); t.set_fontsize(8.5); t.scale(1, 1.5)
    a.set_title(f"SHELL: lift {sh['lift_kgf']:.0f} kgf static / {sh['lift_dyn_kgf']:.0f} kgf pouring → 12 mm, glued + backed; ribs ×{sh['ribs']['I_gain']:.1f} stiffness", loc="left", fontsize=10)
tb(fig, 3, nsheets, "temperature distribution, pouring window, shell"); pdf.savefig(fig); plt.close(fig)
# ---------------- 4 cope sections ----------------
if nsheets == 4:
    import trimesh
    m = trimesh.load(C.out_path(cfg, "cope_shell.stl")); fig, axs = plt.subplots(3, 1, figsize=(16.5, 11.7))
    yc = lay["rows_y"][len(lay["rows_y"]) // 2]; xr = sorted(r[0] for r in lay["risers"] if abs(r[1] - yc) < 0.1 and r[0] > 0)[0]
    xc = sorted(c[0] for c in lay["casts"] if not c[2] and c[0] > 0)[0]
    for ax, (axis, pos, ttl) in zip(axs, ((1, yc, f"along centre runner line Y={yc:.1f}"), (0, xr, f"through first riser X={xr:.1f}"), (0, xc, f"through casting bore X={xc:.1f}"))):
        n = [0, 0, 0]; n[axis] = 1; o = [0, 0, 0]; o[axis] = pos; sec = m.section(plane_origin=o, plane_normal=n)
        if sec is None: continue
        other = 1 - axis
        for e in sec.entities:
            p = sec.vertices[e.points]; ax.plot(p[:, other], p[:, 2], color="#5a4a2a", lw=0.8)
        ax.axhline(0, color="k", lw=0.5, ls="-."); ax.set_aspect("equal"); ax.grid(alpha=.25); ax.set_title("COPE SECTION " + ttl, loc="left", fontsize=9)
        if axis == 0: ax.set_xlim(yc - 90, yc + 90)
    tb(fig, 4, nsheets, "cope shell sections"); pdf.savefig(fig); plt.close(fig)
pdf.close(); print("written", C.out_path(cfg, "gating_layout.pdf"))
