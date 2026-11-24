"""Step 7b - cope (top half) shell mould solid for a horizontal core shooter.

python3 build_cope.py job.json [--bay]          # needs <out>/layout.json and <out>/gating_only.step

Shell = [parting slab (thickness t) + rim + rib grid + conformal bosses] - [casting cope halves + core-print seats
        + gating metal + riser vents + sprue opening + locating dimples], all clipped to Z >= 0.
Conformal boss over a casting = spherical grey-dilation (radius t) of the cope-side height field, built as 2 mm terraces
(always >= t). Gating bosses: risers r+t capsule, runners r+t cylinders, filter well +t, sprue cone +t.
Core-print seat = local box shell.core_box [x0,x1,y0,y1,0,z_top] minus the casting: set z_top ABOVE the highest pocket
ceiling so the core fills the pocket (otherwise thin sand fins remain), and keep prints of neighbouring castings >= 5 mm apart.
--bay builds only the centre bay (fast check). Writes cope_shell.step (+ .stl) and cope.json.
"""
import sys, json, math, argparse, time
import numpy as np
from scipy import ndimage
from skimage import measure
from shapely.geometry import Polygon, MultiPolygon
from shapely.geometry.polygon import orient
import castlib as C
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace, BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.gp import gp_Pnt, gp_Trsf, gp_Vec

ap = argparse.ArgumentParser(); ap.add_argument("job"); ap.add_argument("--bay", action="store_true"); a = ap.parse_args()
cfg = C.load_config(a.job); lay = C.read_json(cfg, "layout.json"); SH = cfg.get("shell", {})
T0 = time.time()
def log(*x): print(f"[{time.time()-T0:6.1f}s]", *x, flush=True)
TH, RW, RH, RIM = SH.get("thickness", 12.0), SH.get("rib_w", 8.0), SH.get("rib_h", 15.0), SH.get("rim_w", 25.0)
PX, PY = cfg.get("plate", {}).get("x", 750.0) / 2, cfg.get("plate", {}).get("y", 650.0) / 2
rows = lay["rows_y"]; casts = [tuple(c) for c in lay["casts"]]; risers = [tuple(r) for r in lay["risers"]]
R = lay["riser"]["D"] / 2; RZ1 = lay["riser"]["z1"]; ext = lay["casting_extent"]
CORE = SH.get("core_box")      # [x0,x1,y0,y1,z0,z1] casting-local, or null when the part needs no core in the cope

# ---------------- print-overlap check between neighbouring castings ----------------
if CORE:
    # lower casting of row j+1 (unrotated, origin rows[j+1]-YR) vs upper casting of row j (rotated, origin rows[j]+YR)
    if len(rows) > 1:
        lo_edge = (rows[1] - lay["yr"]) + CORE[2]; up_edge = (rows[0] + lay["yr"]) - CORE[2]
        sand = lo_edge - up_edge
        print(f"sand between core prints of neighbouring rows: {sand:.1f} mm")
        if sand < 5: print("WARNING: core prints of neighbouring castings are closer than 5 mm - shorten core_box y0")

# ---------------- conformal envelope over one casting (terraces) ----------------
F, fo, fp = C.fine_voxels(cfg)
z = fo[2] + np.arange(F.shape[2]) * fp
Mc = F & (z >= 0)[None, None, :]
h = np.where(Mc.any(2), fo[2] + (F.shape[2] - 1 - np.argmax(Mc[:, :, ::-1], axis=2)) * fp, -1000.0)
pad = int(np.ceil(TH / fp)) + 2; h = np.pad(h, pad, constant_values=-1000.0); ox, oy = fo[0] - pad * fp, fo[1] - pad * fp
r = int(np.ceil(TH / fp)); yy, xx = np.mgrid[-r:r + 1, -r:r + 1] * fp; dd = np.hypot(xx, yy)
fpn = dd <= TH; K = np.where(fpn, np.sqrt(np.clip(TH * TH - dd * dd, 0, None)), 0.0)
E = ndimage.grey_dilation(h, footprint=fpn, structure=K, mode="constant", cval=-1000.0)
def poly_face(coords_list):
    def wire(c):
        mp = BRepBuilderAPI_MakePolygon()
        for x, y in c[:-1]: mp.Add(gp_Pnt(x, y, 0))
        mp.Close(); return mp.Wire()
    mf = BRepBuilderAPI_MakeFace(wire(coords_list[0]), True)
    for hole in coords_list[1:]: mf.Add(wire(hole))       # shapely orient(): exterior CCW, holes CW -> no reversal
    return mf.Face()
prisms = []
for zk in np.arange(TH, np.ceil(E.max() / 2) * 2, 2.0):
    mask = E > zk; reg = None
    for c in sorted([Polygon(np.c_[ox + (c[:, 0] - 1) * fp, oy + (c[:, 1] - 1) * fp]).buffer(0)
                     for c in measure.find_contours(np.pad(mask.astype(float), 1), 0.5) if len(c) > 3], key=lambda p: -p.area):
        reg = c if reg is None else reg.symmetric_difference(c)
    if reg is None: continue
    reg = reg.buffer(0.3).buffer(-0.3).simplify(0.25).buffer(0)
    for p in [p for p in getattr(reg, "geoms", [reg]) if p.area > 5]:
        p = orient(Polygon(p.exterior, [hh for hh in p.interiors if Polygon(hh).area > 5]), 1.0)
        f = poly_face([list(p.exterior.coords)] + [list(i.coords) for i in p.interiors])
        tr = gp_Trsf(); tr.SetTranslation(gp_Vec(0, 0, float(zk)))
        prisms.append(BRepPrimAPI_MakePrism(BRepBuilderAPI_Transform(f, tr, True).Shape(), gp_Vec(0, 0, 2.0)).Shape())
bad = [i for i, p in enumerate(prisms) if not C.valid(p)]
if bad: raise RuntimeError(f"invalid terrace prisms {bad} - check polygon orientation / simplification")
extra = [C.box(CORE[0] - TH, CORE[1] + TH, CORE[2] - TH, CORE[3] + TH / 2, 0, CORE[5] + TH)] if CORE else []
env_local = C.fuse(prisms + extra); assert C.valid(env_local)
cope_part = C.boolop("common", C.load_part(cfg), [C.box(-500, 500, -500, 500, 0, 500)])
core_local = C.box(*CORE) if CORE else None
log(f"casting envelope {C.vol(env_local)/1000:.1f} cm3, terraces {len(prisms)}")

# ---------------- region ----------------
if a.bay:
    yc = rows[len(rows) // 2]; XL, XH, YL, YH = 0.0, 250.0, yc - 80, yc + 80
    casts = [c for c in casts if XL + 40 < c[0] < XH - 50 and YL < c[1] < YH]; risers = [p for p in risers if XL + 40 < p[0] < XH - 10 and abs(p[1] - yc) < 1]
else:
    XL, XH, YL, YH = -PX, PX, -PY, PY
RIBS_Y = SH.get("ribs_y") or ([(a_ + b_) / 2 for a_, b_ in zip(rows[:-1], rows[1:])] + [-(PY - RIM - 25), PY - RIM - 25])
RIBS_X = SH.get("ribs_x") or [x for x in np.arange(-PX + 100, PX - 99, SH.get("rib_pitch", 120.0)) if abs(x) > 45]

pos = [C.box(XL, XH, YL, YH, 0, TH)]
if not a.bay:
    pos += [C.box(-PX, PX, -PY, -PY + RIM, TH, TH + RH), C.box(-PX, PX, PY - RIM, PY, TH, TH + RH),
            C.box(-PX, -PX + RIM, -PY, PY, TH, TH + RH), C.box(PX - RIM, PX, -PY, PY, TH, TH + RH)]
pos += [C.box(XL, XH, y - RW / 2, y + RW / 2, TH, TH + RH) for y in RIBS_Y if YL < y < YH]
pos += [C.box(x - RW / 2, x + RW / 2, YL, YH, TH, TH + RH) for x in RIBS_X if XL < x < XH]
pos += [C.placed(env_local, *c) for c in casts]
pos += [C.capsule(x, y, lay["riser"]["z0"] - TH, RZ1 + TH, R + TH) for x, y in risers]
bR = lay["branch"]["root_d"] / 2
for yc in rows:
    for s in (1, -1):
        x0 = 33.0 if abs(yc) < 45 else 0.0
        a_, b_ = sorted([s * x0, s * lay["run_end"]]); a_, b_ = max(a_, XL - 20), min(b_, XH + 20)
        if b_ > a_ and YL - 30 < yc < YH + 30: pos.append(C.cyl((a_, yc, 0), (1, 0, 0), bR + TH, b_ - a_))
if not a.bay:
    ymax = max(rows) + 25.0; cR = lay["cross"]["root_d"] / 2
    pos += [C.cyl((0, -ymax, 0), (0, 1, 0), cR + TH, 2 * ymax), C.box(-25 - TH, 25 + TH, -25 - TH, 25 + TH, 0, 8 + TH),
            C.cone((0, 0, 0), lay["choke_dia_mm"] / 2 + TH, lay["sprue_top_dia_mm"] / 2 + TH, 50.0)]
env = C.boolop("common", C.fuse(pos), [C.box(XL, XH, YL, YH, 0, RZ1 + TH + 40)])
log("envelope valid:", C.valid(env))
tools = []
for c in casts:
    tools.append(C.placed(cope_part, *c))
    if core_local is not None: tools.append(C.placed(core_local, *c))
GAT = C.read_step(C.out_path(cfg, "gating_only.step"))
if a.bay: GAT = C.boolop("common", GAT, [C.box(XL - 1, XH + 1, YL - 1, YH + 1, -60, 200)])
tools.append(GAT)
vent = SH.get("riser_vent_d", 4.0)
tools += [C.cyl((x, y, RZ1 - 6), (0, 0, 1), vent / 2, TH + 30) for x, y in risers]
if not a.bay:
    tools.append(C.cone((0, 0, 49.0), lay["sprue_top_dia_mm"] / 2, lay["sprue_top_dia_mm"] / 2 + 2, 40.0))
    for sx in (-1, 1):
        for sy in (-1, 1): tools.append(C.cone((sx * (PX - 13), sy * (PY - 13), 0.0), 8.0, 6.0, 8.0))
shell = C.boolop("cut", env, tools)
u = ShapeUpgrade_UnifySameDomain(shell, True, True, True); u.Build(); shell = u.Shape()
V = C.vol(shell); ok = C.valid(shell)
log(f"cope shell valid {ok}, volume {V/1e6:.2f} L -> sand ~ {V*SH.get('sand_density', 1550.0)/1e9:.1f} kg")
name = "cope_shell_bay" if a.bay else "cope_shell"
C.write_step(shell, C.out_path(cfg, name + ".step")); C.mesh_to_stl(shell, C.out_path(cfg, name + ".stl"), 0.5, 0.5)
C.save_json(cfg, name + ".json", dict(volume_L=V / 1e6, sand_kg=V * SH.get("sand_density", 1550.0) / 1e9, valid=ok, ribs_x=list(map(float, RIBS_X)),
                                      ribs_y=list(map(float, RIBS_Y)), thickness=TH, rib=[RW, RH], rim=RIM, core_box=CORE))
log("written", name + ".step")
