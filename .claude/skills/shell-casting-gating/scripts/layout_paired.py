"""Step 4 - plate layout, gating system, weights / yield, choke, STEP output.

python3 layout_paired.py job.json [--no-step]

Arrangement ("paired across a runner", proven on the rocker-lever job):
  * horizontal parting Z=0, central sprue + horizontal ceramic-foam filter at the plate centre,
    cross runner along Y (stepped), branch runners along X (stepped, constant velocity) at every row line,
  * on every branch: castings below the runner (unrotated, feeding face +Y up) and above it (rotated 180 deg about Z,
    shifted in X by `shift` so their necks line up), one blind riser per neck pair sitting ON the runner (hot riser),
  * cold-metal well (vertical sump in the drag) at every runner end.
Writes <out>/layout.json, gating_only.step and layout_assembly.step (instanced: 1 casting part x N + gating body).
"""
import sys, json, math, argparse
import numpy as np
import castlib as C
from feeder_sim import cell_design
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

ap = argparse.ArgumentParser(); ap.add_argument("job"); ap.add_argument("--no-step", action="store_true"); a = ap.parse_args()
cfg = C.load_config(a.job)
part = cfg["part"]; fd = cfg["feeding"]; L = cfg.get("layout", {}); PO = cfg.get("pouring", {})
rho_s, rho_l = part.get("rho_solid", 7.1), part.get("rho_liquid", 7.0)
PX, PY = cfg.get("plate", {}).get("x", 750.0), cfg.get("plate", {}).get("y", 650.0); MARGIN = cfg.get("plate", {}).get("margin", 30.0)
S = C.load_part(cfg); V_CAST = C.vol(S); (cx0, cy0, cz0), (cx1, cy1, cz1) = C.bbox(S)
F, fo, fp = C.fine_voxels(cfg); idx = np.argwhere(F); pts = fo + idx * fp
CXMIN, CYMIN, CZMIN = pts.min(0) - fp / 2; CXMAX, CYMAX, CZMAX = pts.max(0) + fp / 2
cd = cell_design(cfg); YR, SHIFT, R = cd["YR"], cd["shift"], cd["R"]
RZ0, RZ1 = fd["riser"]["z0"], fd["riser"]["z1"]
CAST_GAP, ROW_GAP, X_START = L.get("cast_gap", 15.0), L.get("row_gap", 19.0), L.get("x_start", 55.0)
B_ROOT, B_MIN = L.get("branch_root_d", 16.0), L.get("branch_min_d", 10.0)
C_ROOT, C_TIP = L.get("cross_root_d", 22.0), L.get("cross_tip_d", 16.0)
WELL = L.get("well", {"d": 10.0, "depth": 25.0})
LIM_X, LIM_Y = PX / 2 - MARGIN, PY / 2 - MARGIN

# ------------------------------------------------------------- positions
pitch_x = (CXMAX - CXMIN) + CAST_GAP
dr_span = (YR - CYMIN) * 2; pitch_y = dr_span + ROW_GAP
n_rows = L.get("rows") or max(1, int((2 * LIM_Y - dr_span) // pitch_y) + 1)
rows = [(j - (n_rows - 1) / 2) * pitch_y for j in range(n_rows)]
right0 = X_START - min(CXMIN, SHIFT - CXMAX); left0 = -X_START - max(CXMAX, SHIFT - CXMIN)
def ext_right(xo): return max(xo + CXMAX, xo + SHIFT - CXMIN, max(xo + r for r in [n["x"] for n in fd["necks"]] + [SHIFT - n["x"] for n in fd["necks"]]) + R)
def ext_left(xo): return min(xo + CXMIN, xo + SHIFT - CXMAX, min(xo + r for r in [n["x"] for n in fd["necks"]] + [SHIFT - n["x"] for n in fd["necks"]]) - R)
n_half = L.get("per_half")
if not n_half:
    n_half = 0
    while ext_right(right0 + n_half * pitch_x) <= LIM_X and ext_left(left0 - n_half * pitch_x) >= -LIM_X: n_half += 1
xs_lower = [right0 + k * pitch_x for k in range(n_half)] + [left0 - k * pitch_x for k in range(n_half)]
casts, risers, necks = [], [], []
for yc in rows:
    for xo in xs_lower:
        casts += [(xo, yc - YR, False), (xo + SHIFT, yc + YR, True)]
        for xr in cd["risers"]: risers.append((xo + xr, yc))
        for n in fd["necks"]:
            necks.append((xo + n["x"], n, yc - YR + n["face_y"] - 1, yc))
            necks.append((xo + SHIFT - n["x"], n, yc + YR - n["face_y"] + 1, yc))
y_ext = max(rows) + YR - CYMIN
x_ext = max(ext_right(x) for x in xs_lower if x > 0)
print(f"cavities {len(casts)} ({n_rows} rows x {2*n_half} pairs), risers {len(risers)}, X extent ±{x_ext:.1f} (limit {LIM_X}), Y extent ±{y_ext:.1f} (limit {LIM_Y})")
if y_ext > LIM_Y + 0.5 or x_ext > LIM_X + 0.5: print("WARNING: layout exceeds the usable plate area")

# ------------------------------------------------------------- gating solids
Z_CUP_TOP, Z_SPRUE_TOP, Z_WELL_TOP, Z_FILT_BOT, Z_CH_BOT = PO.get("cup_top_z", 100.0), PO.get("sprue_top_z", 50.0), 8.0, -22.0, -32.0
FILT = PO.get("filter_size_mm", 50.0); CH = FILT / 2 - 4
RUN_END = min(LIM_X + 4, PX / 2 - 26)
def gating(r_choke):
    r_top = r_choke * ((Z_CUP_TOP - 5 - Z_WELL_TOP) / (Z_CUP_TOP - 5 - Z_SPRUE_TOP)) ** 0.25
    P = dict(cup=C.cone((0, 0, Z_SPRUE_TOP), r_top, 35.0, Z_CUP_TOP - Z_SPRUE_TOP), sprue=C.cone((0, 0, Z_WELL_TOP), r_choke, r_top, Z_SPRUE_TOP - Z_WELL_TOP),
             well=C.box(-FILT / 2, FILT / 2, -FILT / 2, FILT / 2, 0, Z_WELL_TOP), chamber=C.box(-CH, CH, -CH, CH, Z_CH_BOT, Z_FILT_BOT))
    run, wells, warn = [], [], []
    ymax = max(rows) + 25.0
    side_rows = sorted({abs(y) for y in rows if abs(y) > 45})
    for s in (1, -1):
        run += [C.box(-11, 11, s * (CH - 1), s * 45, Z_CH_BOT, Z_FILT_BOT), C.box(-10, 10, s * 33, s * 45, Z_FILT_BOT, 0),
                C.box(s * (CH - 1), s * 45, -9, 9, Z_CH_BOT, Z_FILT_BOT), C.box(s * 33, s * 45, -9, 9, Z_FILT_BOT, 0)]
        if side_rows:
            pts_ = [33.0] + side_rows + [ymax]
            nmax = len(side_rows)
            for i in range(len(pts_) - 1):
                n_down = max(nmax - i, 1); dd = max(C_TIP, C_ROOT * math.sqrt(n_down / nmax)) if i < nmax else C_TIP
                a_, b_ = pts_[i], pts_[i + 1]
                run.append(C.cyl((0, min(s * a_, s * b_), 0), (0, 1, 0), dd / 2, b_ - a_))
            wells.append(C.cyl((0, s * (ymax - 8), -32), (0, 0, 1), WELL["d"] / 2 + 3, 32))
    for yc in rows:
        for s in (1, -1):
            xs = sorted([abs(r[0]) for r in risers if abs(r[1] - yc) < 0.1 and math.copysign(1, r[0]) == s])
            x0 = 33.0 if abs(yc) < 45 else 0.0
            pts_ = [x0] + xs
            for i in range(len(xs)):
                n = len(xs) - i; dd = max(B_MIN, B_ROOT * math.sqrt(n / len(xs)))
                run.append(C.cyl((min(s * pts_[i], s * pts_[i + 1]), yc, 0), (1, 0, 0), dd / 2, pts_[i + 1] - pts_[i]))
            run.append(C.cyl((min(s * xs[-1], s * RUN_END), yc, 0), (1, 0, 0), B_MIN / 2, RUN_END - xs[-1]))
            xw = RUN_END - WELL["d"] / 2
            gap = xw - WELL["d"] / 2 - (xs[-1] + math.sqrt(max(R ** 2 - 7 ** 2, 0)))
            if gap >= 3.0:
                wells.append(C.cyl((s * xw, yc, -7 - WELL["depth"]), (0, 0, 1), WELL["d"] / 2, WELL["depth"] + 7))
            else:
                warn.append(f"no room for cold-metal well at row {yc:.1f} (gap {gap:.1f} mm)")
    P["runners"] = run + wells; P["n_wells"] = len(wells); P["warn"] = warn
    P["risers"] = [C.capsule(x, y, RZ0, RZ1, R) for x, y in risers]
    P["necks"] = [C.box(x - n["w"] / 2, x + n["w"] / 2, y0, y1, -n["t"] / 2, n["t"] / 2) for x, n, y0, y1 in necks]
    return P, r_top

def weights(P):
    runners = C.fuse(P["runners"]); ris = C.fuse(P["risers"])
    v = dict(cup=C.vol(P["cup"]) * 0.35, sprue=C.vol(P["sprue"]), filter_area=C.vol(P["well"]) + C.vol(P["chamber"]) + FILT * FILT * 22 * 0.8,
             runners=C.vol(runners), risers=C.vol(C.fuse([ris, runners])) - C.vol(runners),
             necks=sum(n["w"] * n["t"] * max(abs(y1 - y0) - R - 1, 0) for x, n, y0, y1 in necks))
    return v, runners, ris

T_FILL = PO.get("fill_time_s", 11.0); CD = PO.get("discharge_coeff", 0.75); T_SEC = PO.get("governing_section_mm", 8.0); K = PO.get("fluidity_K", 1.0)
He = (Z_CUP_TOP - 5 - Z_WELL_TOP) / 1000 - ((CZMAX / 1000) ** 2) / (2 * (CZMAX - CZMIN) / 1000)
r_c = 9.5
for it in range(3):
    P, r_top = gating(r_c); v, runners, ris = weights(P)
    Wc = len(casts) * V_CAST * rho_s / 1e6; W = Wc + sum(v.values()) * rho_s / 1e6
    Ac = W * 1000 / (rho_l * T_FILL * CD * math.sqrt(2 * 9.81 * He) * 100); r_c = math.sqrt(Ac * 100 / math.pi)
P, r_top = gating(r_c); v, runners, ris = weights(P)
Wc = len(casts) * V_CAST * rho_s / 1e6; W = Wc + sum(v.values()) * rho_s / 1e6
t_dietert = K * (1.41 + T_SEC / 14.59) * math.sqrt(W * 2.2046)
Q = W * 1000 / rho_l / T_FILL
cap, rate = PO.get("filter_capacity_kg", 40.0), PO.get("filter_rate_kg_s", 4.0)
for w_ in P["warn"]: print("WARNING:", w_)

# ------------------------------------------------------------- clearance check on one bay
bay_c = [c for c in casts if abs(c[1] - (rows[len(rows) // 2] - YR)) < 0.5 or abs(c[1] - (rows[len(rows) // 2] + YR)) < 0.5]
bay_c = sorted([c for c in bay_c if c[0] > 0], key=lambda c: c[0])[:4]
inst = {c: C.placed(S, *c) for c in bay_c}
yc = rows[len(rows) // 2]
clear = {}
run_cyl = C.cyl((0, yc, 0), (1, 0, 0), B_ROOT / 2, RUN_END)
clear["runner_to_casting"] = min(BRepExtrema_DistShapeShape(run_cyl, s).Value() for s in inst.values())
lo_b = [c for c in bay_c if not c[2]]; up_b = [c for c in bay_c if c[2]]
if len(lo_b) > 1: clear["casting_to_casting_along_row"] = BRepExtrema_DistShapeShape(inst[lo_b[0]], inst[lo_b[1]]).Value()
if len(rows) > 1:
    other = [c for c in casts if c[2] and abs(c[1] - (rows[len(rows) // 2 - 1] + YR)) < 0.5 and c[0] > 0]
    if other:
        o_ = min(other, key=lambda c: abs(c[0] - lo_b[0][0]))
        clear["casting_to_casting_between_rows"] = BRepExtrema_DistShapeShape(inst[lo_b[0]], C.placed(S, *o_)).Value()
rr = [r for r in risers if abs(r[1] - yc) < 0.1 and r[0] > 0][:3]
clear["riser_to_nearest_casting_(neck_gap)"] = min(BRepExtrema_DistShapeShape(C.capsule(x, y, RZ0, RZ1, R), s).Value() for x, y in rr for s in inst.values())
print("clearances (mm):", {k: round(x, 1) for k, x in clear.items()})
min_sand = L.get("min_sand_mm", 5.0)
if clear["runner_to_casting"] < min_sand: print(f"WARNING: runner closer than {min_sand} mm to a casting")

res = dict(cavities=len(casts), rows=n_rows, pairs_per_row=2 * n_half, casting_kg=V_CAST * rho_s / 1e6, castings_total_kg=Wc,
           gating_breakdown_kg={k: x * rho_s / 1e6 for k, x in v.items()}, poured_kg=W, yield_pct=100 * Wc / W,
           fill_time_s=T_FILL, dietert_time_s=t_dietert, fill_rate_kg_s=W / T_FILL, H_eff_mm=He * 1000, choke_area_cm2=Ac,
           choke_dia_mm=2 * r_c, sprue_top_dia_mm=2 * r_top, Q_cm3_s=Q, rows_y=rows, casts=casts, risers=risers, run_end=RUN_END,
           yr=YR, shift=SHIFT, riser=dict(D=2 * R, z0=RZ0, z1=RZ1), riser_vol_cm3=v["risers"] / len(risers) / 1000,
           branch=dict(root_d=B_ROOT, min_d=B_MIN), cross=dict(root_d=C_ROOT, tip_d=C_TIP), wells=P["n_wells"],
           casting_extent=dict(xmin=float(CXMIN), xmax=float(CXMAX), ymin=float(CYMIN), ymax=float(CYMAX), zmin=float(CZMIN), zmax=float(CZMAX)),
           clearances_mm=clear, filter=dict(capacity_kg=cap, rate_kg_s=rate, ok=bool(W <= cap and W / T_FILL <= rate)), warnings=P["warn"])
C.save_json(cfg, "layout.json", res)
print(json.dumps({k: (round(x, 3) if isinstance(x, float) else x) for k, x in res.items() if k not in ("casts", "risers", "rows_y")}, indent=1))
if not res["filter"]["ok"]: print("WARNING: poured weight or fill rate exceeds the filter rating - use a bigger filter")

if not a.no_step:
    gat = C.fuse([P["cup"], P["sprue"], P["well"], P["chamber"], runners, ris] + P["necks"])
    C.write_step(gat, C.out_path(cfg, "gating_only.step"))
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.TDocStd import TDocStd_Document
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    from OCP.TDataStd import TDataStd_Name
    from OCP.TopLoc import TopLoc_Location
    from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir, gp_Vec
    from OCP.STEPControl import STEPControl_AsIs
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF")); st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    asm = st.NewShape(); TDataStd_Name.Set_s(asm, TCollection_ExtendedString("GATING_LAYOUT"))
    cl = st.AddShape(S, False); TDataStd_Name.Set_s(cl, TCollection_ExtendedString("CASTING"))
    gl = st.AddShape(gat, False); TDataStd_Name.Set_s(gl, TCollection_ExtendedString("GATING_AND_RISERS"))
    for xo, yo, rot in casts:
        tr = gp_Trsf()
        if rot: tr.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.pi)
        t2 = gp_Trsf(); t2.SetTranslation(gp_Vec(xo, yo, 0)); t2.Multiply(tr); st.AddComponent(asm, cl, TopLoc_Location(t2))
    st.AddComponent(asm, gl, TopLoc_Location()); st.UpdateAssemblies()
    w = STEPCAFControl_Writer(); w.SetNameMode(True); w.Transfer(doc, STEPControl_AsIs); w.Write(C.out_path(cfg, "layout_assembly.step"))
    print("STEP written: gating_only.step, layout_assembly.step")
