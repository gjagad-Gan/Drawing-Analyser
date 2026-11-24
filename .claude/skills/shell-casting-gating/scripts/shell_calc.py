"""Step 7a - shell thickness / hold-down / rib stiffness check for a flat horizontal shell mould.

python3 shell_calc.py job.json      # uses <out>/layout.json

Lift on cope = rho_metal * g * (metal head above each cavity roof) * roof area (casting roofs ~ top of casting, risers,
runners), x1.5 pour-impact factor. Plate formulas: simply supported 2-edge strip for handling sag, simply supported
rectangle (a/b~1.15) for "held at edges only", clamped strip over one cavity for local roof stress.
Writes <out>/shell.json.
"""
import sys, json, math, numpy as np
import castlib as C

cfg = C.load_config(sys.argv[1]); lay = C.read_json(cfg, "layout.json"); SH = cfg.get("shell", {})
PX, PY = cfg.get("plate", {}).get("x", 750.0) / 1000, cfg.get("plate", {}).get("y", 650.0) / 1000
rho_sh, E, nu, MOR = SH.get("sand_density", 1550.0), SH.get("E_Pa", 4.0e9), 0.25, SH.get("MOR_Pa", 3.0e6)
F, fo, fp = C.fine_voxels(cfg)
A_cast = F.any(axis=2).sum() * fp * fp * 1e-6
n = lay["cavities"]; nr = len(lay["risers"]); rD = lay["riser"]["D"] / 1000
A_ris = nr * math.pi * (rD / 2) ** 2
xspan = 2 * lay["run_end"] / 1000; yspan = 2 * (max(lay["rows_y"]) + 25) / 1000
A_run = len(lay["rows_y"]) * xspan * lay["branch"]["root_d"] / 1000 * 0.8 + yspan * lay["cross"]["root_d"] / 1000 * 0.8 + 0.05 * 0.05
H = (cfg.get("pouring", {}).get("cup_top_z", 100.0) - 5) / 1000; ztop = lay["casting_extent"]["zmax"] / 1000
F_lift = 7000 * 9.81 * (n * A_cast * (H - 0.7 * ztop) + A_ris * max(H - lay["riser"]["z1"] / 1000, 0.0) * 0.6 + A_run * (H - 0.010))
F_dyn = 1.5 * F_lift; A_plate = PX * PY
def T_I(bw, t, rw, rh):
    A1, y1 = bw * t, t / 2; A2, y2 = rw * rh, t + rh / 2; yb = (A1 * y1 + A2 * y2) / (A1 + A2)
    return bw * t ** 3 / 12 + A1 * (y1 - yb) ** 2 + rw * rh ** 3 / 12 + A2 * (y2 - yb) ** 2
rows = []
for t_mm in (8, 10, 12, 14, 16):
    t = t_mm / 1000; W = rho_sh * A_plate * t * 1.25 * 9.81
    q = rho_sh * 9.81 * t; sag = 5 * q * PY ** 4 / (384 * E * t ** 3 / 12) * 1000; sig_h = 0.75 * rho_sh * 9.81 * PY ** 2 / t
    qu = F_dyn / A_plate; Dp = E * t ** 3 / (12 * (1 - nu ** 2)); w_up = 0.0050 * qu * PY ** 4 / Dp * 1000; sig_up = 6 * 0.053 * qu * PY ** 2 / t ** 2
    p_loc = 7000 * 9.81 * (H - 0.7 * ztop) * 1.5; sig_loc = 0.5 * p_loc * (2 * abs(lay["casting_extent"]["ymin"]) / 1000) ** 2 / t ** 2
    rows.append(dict(t=t_mm, cope_kg=W / 9.81, sag_handling_mm=sag, SF_handling=MOR / sig_h, bow_edges_only_mm=w_up, SF_edges_only=MOR / sig_up,
                     local_roof_kPa=sig_loc / 1000, hold_down_kgf=(F_dyn - W) / 9.81))
t0 = SH.get("thickness", 12.0); rw, rh, pitch = SH.get("rib_w", 8.0), SH.get("rib_h", 15.0), SH.get("rib_pitch", 120.0)
I0 = pitch * t0 ** 3 / 12; I1 = T_I(pitch, t0, rw, rh)
res = dict(A_proj_cm2=(n * A_cast + A_ris + A_run) * 1e4, lift_kgf=F_lift / 9.81, lift_dyn_kgf=F_dyn / 9.81, rows=rows,
           ribs=dict(thickness=t0, rib_w=rw, rib_h=rh, pitch=pitch, I_gain=I1 / I0,
                     bow_edges_only_with_ribs_mm=[r for r in rows if r["t"] == int(t0)][0]["bow_edges_only_mm"] * I0 / I1 if int(t0) in (8, 10, 12, 14, 16) else None))
print(f"lift on cope {res['lift_kgf']:.0f} kgf static, {res['lift_dyn_kgf']:.0f} kgf with impact")
for r in rows:
    print(f"t={r['t']:2d}: cope {r['cope_kg']:.1f} kg | handling sag {r['sag_handling_mm']:.2f} mm SF {r['SF_handling']:.1f} | edges-only bow {r['bow_edges_only_mm']:.1f} mm SF {r['SF_edges_only']:.1f} | local roof {r['local_roof_kPa']:.0f} kPa | hold-down {r['hold_down_kgf']:.0f} kgf")
print(f"ribs {rw}x{rh} @ {pitch}: stiffness x{I1/I0:.2f}")
C.save_json(cfg, "shell.json", res)
