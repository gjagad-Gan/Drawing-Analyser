"""Step 3 - solidification check of the feeding design (one 'cell': two castings sharing risers on one runner).

python3 feeder_sim.py job.json                      # nominal + cold-runner case
python3 feeder_sim.py job.json --sweep 1300,1360,1420,1450   # in-mould temperature sweep (also cold variant)

Cell geometry (casting-local frame: parting Z=0, feeding face +Y):
  casting A at (0,0); casting B rotated 180 deg about Z at (shift, 2*YR) so its necks line up with A's;
  riser centre line Y = YR = max(face_y) + neck_gap + D/2; runner along X through the riser bases.
Model: explicit enthalpy finite-volume heat conduction on a 1 mm grid (numba), shell sand around, metal latent heat
released linearly between T_solidus and T_liquidus. Results are THERMAL only (no graphite expansion, no mould movement).

Reported per case (worst arm):
  unfed_mm3        casting volume with no open feed path to a feeder when it reaches fs=0.7  (must be 0)
  neck_vs_arm      time the best path through a neck closes / hot-spot time of the arm away from the neck (>= 1.10, aim 1.14)
  riser_vs_neck    riser last-freeze time / neck closing time (>= 1.30)
Do NOT use "hottest neck cell / hottest casting cell" - the neck heats the casting at the contact, the ratio is meaningless.
"""
import sys, json, math, argparse, numpy as np
import numba as nb
from scipy import ndimage
from skimage.morphology import reconstruction
import castlib as C

DEF = dict(T_liquidus=1160.0, T_solidus=1120.0, latent=230e3, rho_m=7000.0, cp_m=800.0, k_m=32.0,
           rho_s=1500.0, cp_s=1100.0, k_s=0.7, T_mould=50.0, fs_crit=0.7, dx=1.0, T_in_mould=1370.0, cold_delta=-70.0)

# ------------------------------------------------------------------ geometry
def cell_design(cfg):
    fd = cfg["feeding"]; necks = fd["necks"]; R = fd["riser"]["D"] / 2
    YR = max(n["face_y"] for n in necks) + fd.get("neck_gap", 5.0) + R
    xs = [n["x"] for n in necks]
    shift = fd.get("shift", (min(xs) + max(xs)) if len(xs) == 2 else 0.0)
    rx_A = [n["x"] for n in necks]; rx_B = [shift - n["x"] for n in necks]
    risers = sorted(set(round(x, 2) for x in rx_A + rx_B))
    merged = []
    for x in risers:
        if not merged or abs(x - merged[-1]) > 1.0: merged.append(x)
    return dict(YR=YR, shift=shift, risers=merged, necks=necks, R=R)

def prim_mask(p, lo, shape, dx):
    X, Y, Z = [lo[a] + (np.arange(shape[a]) + 0.5) * dx for a in range(3)]
    gx, gy, gz = np.meshgrid(X, Y, Z, indexing="ij"); t = p["type"]; b = p["b"]
    if t == "box":
        return (gx >= min(b[0], b[1])) & (gx <= max(b[0], b[1])) & (gy >= min(b[2], b[3])) & (gy <= max(b[2], b[3])) & (gz >= b[4]) & (gz <= b[5])
    if t == "cylx":
        return (gx >= min(b[0], b[1])) & (gx <= max(b[0], b[1])) & ((gy - b[2]) ** 2 + (gz - b[3]) ** 2 <= b[4] ** 2)
    if t == "dome":
        zc = np.clip(gz, b[2] + b[4], b[3] - b[4])
        return (gx - b[0]) ** 2 + (gy - b[1]) ** 2 + (gz - zc) ** 2 <= b[4] ** 2
    raise ValueError(t)

def build_cell(cfg, dx):
    fd = cfg["feeding"]; cd = cell_design(cfg); YR, R, shift = cd["YR"], cd["R"], cd["shift"]
    m, go = C.calibrated_grid(cfg, dx)
    cmin = go; cmax = go + np.array(m.shape) * dx
    z0, z1 = fd["riser"]["z0"], fd["riser"]["z1"]
    lo = np.array([min(cmin[0], shift - cmax[0]) - 20, cmin[1] - 20, min(cmin[2], z0) - 18])
    hi = np.array([max(cmax[0], shift - cmin[0]) + 20, 2 * YR - cmin[1] + 20, max(cmax[2], z1) + 18])
    shape = tuple(np.ceil((hi - lo) / dx).astype(int))
    prims = [dict(type="cylx", b=[lo[0] + 4, hi[0] - 4, YR, 0, fd.get("runner_d", 14) / 2], mat=2)]
    for x in cd["risers"]:
        prims.append(dict(type="dome", b=[x, YR, z0, z1, R], mat=4))
    for n in cd["necks"]:
        prims.append(dict(type="box", b=[n["x"] - n["w"] / 2, n["x"] + n["w"] / 2, n["face_y"] - 1, YR, -n["t"] / 2, n["t"] / 2], mat=3))
        xb = shift - n["x"]
        prims.append(dict(type="box", b=[xb - n["w"] / 2, xb + n["w"] / 2, YR, 2 * YR - n["face_y"] + 1, -n["t"] / 2, n["t"] / 2], mat=3))
    lab = np.zeros(shape, np.int8)
    for p in prims:
        lab[prim_mask(p, lo, shape, dx) & (lab == 0)] = p["mat"]
    cid = np.zeros(shape, np.int8)
    X, Y, Z = [lo[a] + (np.arange(shape[a]) + 0.5) * dx for a in range(3)]
    gx, gy, gz = np.meshgrid(X, Y, Z, indexing="ij")
    for k, (xo, yo, rot) in enumerate(((0.0, 0.0, False), (shift, 2 * YR, True)), 1):
        lx, ly = gx - xo, gy - yo
        if rot: lx, ly = -lx, -ly
        ii = np.floor((lx - go[0]) / dx).astype(int); jj = np.floor((ly - go[1]) / dx).astype(int); kk = np.floor((gz - go[2]) / dx).astype(int)
        ok = (ii >= 0) & (ii < m.shape[0]) & (jj >= 0) & (jj < m.shape[1]) & (kk >= 0) & (kk < m.shape[2])
        cm = np.zeros(shape, bool); cm[ok] = m[ii[ok], jj[ok], kk[ok]]
        lab[cm] = 1; cid[cm] = k
    return lab, cid, lo, cd

# ------------------------------------------------------------------ solver
@nb.njit(parallel=True, fastmath=True)
def _step(H, T, k, dt_dx2, nx, ny, nz):
    Hn = H.copy()
    for i in nb.prange(1, nx - 1):
        for j in range(1, ny - 1):
            for m in range(1, nz - 1):
                kc = k[i, j, m]; tc = T[i, j, m]; q = 0.0
                for (a, b, c) in ((i - 1, j, m), (i + 1, j, m), (i, j - 1, m), (i, j + 1, m), (i, j, m - 1), (i, j, m + 1)):
                    kn = k[a, b, c]; q += 2.0 * kc * kn / (kc + kn) * (T[a, b, c] - tc)
                Hn[i, j, m] = H[i, j, m] + q * dt_dx2
    return Hn

@nb.njit(parallel=True, fastmath=True)
def _temp(H, T, FS, rc, metal, nx, ny, nz, TL, TS, rhoL):
    for i in nb.prange(nx):
        for j in range(ny):
            for m in range(nz):
                h = H[i, j, m]; c = rc[i, j, m]
                if not metal[i, j, m]:
                    T[i, j, m] = h / c; continue
                hs = c * TS; hl = c * TL + rhoL
                if h <= hs: T[i, j, m] = h / c; FS[i, j, m] = 1.0
                elif h >= hl: T[i, j, m] = (h - rhoL) / c; FS[i, j, m] = 0.0
                else:
                    f = (h - hs) / (hl - hs); T[i, j, m] = TS + f * (TL - TS); FS[i, j, m] = 1.0 - f

def simulate(lab, P, t_cast, t_gate, tmax=1200.0):
    dx = P["dx"] / 1000.0; metal = lab > 0
    k = np.where(metal, P["k_m"], P["k_s"]).astype(np.float64)
    rc = np.where(metal, P["rho_m"] * P["cp_m"], P["rho_s"] * P["cp_s"]).astype(np.float64)
    rhoL = P["rho_m"] * P["latent"]
    T = np.where(metal, t_cast, P["T_mould"]).astype(np.float64); T[lab > 1] = t_gate
    H = np.where(metal, rc * T + rhoL, rc * T); FS = np.zeros_like(T)
    dt = 0.9 * P["rho_m"] * P["cp_m"] * dx * dx / (6 * P["k_m"])
    tc = np.full(T.shape, np.nan); tend = np.full(T.shape, np.nan); nx, ny, nz = T.shape; t = 0.0; it = 0
    while t < tmax:
        H = _step(H, T, k, dt / (dx * dx), nx, ny, nz); _temp(H, T, FS, rc, metal, nx, ny, nz, P["T_liquidus"], P["T_solidus"], rhoL)
        t += dt; it += 1
        if it % 20 == 0:
            new = metal & np.isnan(tc) & (FS >= P["fs_crit"]); tc[new] = t
            new = metal & np.isnan(tend) & (FS >= 0.999); tend[new] = t
            if not np.isnan(tend[metal]).any(): break
    return tc, tend

# ------------------------------------------------------------------ metrics
def unfed(tc, lab):
    f = np.where(lab > 0, np.nan_to_num(tc, nan=0.0), 0.0)
    B = reconstruction(np.where(np.isin(lab, (2, 4)), f, 0.0), f, method="dilation")
    return int(((lab == 1) & (B < f - 1e-6)).sum())

def margins(tc, lab):
    f = np.where(lab > 0, np.nan_to_num(tc, nan=0.0), 0.0)
    feeder = (lab == 4) if (lab == 4).any() else (lab == 2)
    mask = np.where((lab == 3) | (lab == 2) | feeder, f, 0.0)
    B = reconstruction(np.where(feeder | (lab == 2), f, 0.0), mask, method="dilation")
    contact = (lab == 3) & ndimage.binary_dilation(lab == 1)
    g, n = ndimage.label(lab == 3); out = []
    for i in range(1, n + 1):
        c = contact & (g == i)
        if not c.any(): continue
        close = B[c].max(); d = ndimage.distance_transform_edt(~c)
        arm = (lab == 1) & (d > 6) & (d < 25)
        if arm.any(): out.append((float(close), float(f[arm].max())))
    fmax = float(f[feeder].max())
    return dict(neck_vs_arm=min(c / h for c, h in out), riser_vs_neck=min(fmax / c for c, h in out),
                pairs=[(round(c, 1), round(h, 1)) for c, h in out], t_feeder=fmax)

def run_case(cfg, P, t_cast, t_gate, lab_cache={}):
    key = P["dx"]
    if key not in lab_cache: lab_cache[key] = build_cell(cfg, P["dx"])
    lab, cid, lo, cd = lab_cache[key]
    tc, tend = simulate(lab, P, t_cast, t_gate)
    r = dict(T_cast=t_cast, T_gate=t_gate, unfed_mm3=unfed(tc, lab) * P["dx"] ** 3, **margins(tc, lab),
             riser_vol_cm3=float((lab == 4).sum() * P["dx"] ** 3 / max(len(cd["risers"]), 1) / 1000))
    return r, (tc, lab, lo)

def figure(cfg, tc, lab, lo, cd, path):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from skimage import measure
    F = np.where(lab > 0, tc, np.nan); vmax = np.nanmax(F)
    fig, axs = plt.subplots(1, 2, figsize=(16, 7), gridspec_kw=dict(width_ratios=[1.3, 1]))
    for ax, (a, pos, ttl) in zip(axs, ((2, 0.0, "plan on parting Z=0"), (0, cd["risers"][0], f"section X={cd['risers'][0]:.1f} (riser + necks)"))):
        k = int(round(pos - lo[a] - 0.5)); Sx = np.take(F, k, axis=a); L = np.take(lab, k, axis=a); rest = [i for i in range(3) if i != a]
        ext = [lo[rest[0]], lo[rest[0]] + Sx.shape[0], lo[rest[1]], lo[rest[1]] + Sx.shape[1]]
        im = ax.imshow(Sx.T, origin="lower", extent=ext, cmap="turbo", vmin=20, vmax=vmax)
        for c in measure.find_contours(np.pad((L == 1).astype(float), 1), 0.5):
            ax.plot(lo[rest[0]] + c[:, 0] - 0.5, lo[rest[1]] + c[:, 1] - 0.5, color="white", lw=0.8)
        ax.set_title(ttl, loc="left", fontsize=9); ax.set_aspect("equal")
    fig.colorbar(im, ax=axs, shrink=0.75, label="time to 70 % solid (s)")
    fig.suptitle("Feeding cell solidification: thin sections -> arms -> necks -> risers should freeze in that order", x=0.02, ha="left")
    fig.savefig(path, dpi=100, bbox_inches="tight"); plt.close(fig)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("job"); ap.add_argument("--sweep", default=""); a = ap.parse_args()
    cfg = C.load_config(a.job); P = dict(DEF, **cfg.get("simulation", {}))
    cd = cell_design(cfg)
    print(f"cell: riser centre line YR={cd['YR']:.2f}, B-casting shift {cd['shift']:.2f}, risers at X {cd['risers']}")
    out = dict(cell=cd, cases=[])
    temps = [float(t) for t in a.sweep.split(",") if t] or [P["T_in_mould"]]
    for T in temps:
        for dg in (0.0, P["cold_delta"]):
            r, (tc, lab, lo) = run_case(cfg, P, T, T + dg)
            out["cases"].append(r)
            print(f"in-mould {T:.0f} gating {dg:+.0f}: unfed {r['unfed_mm3']:.0f} mm3 | neck/arm {r['neck_vs_arm']:.2f} | riser/neck {r['riser_vs_neck']:.2f} | riser {r['riser_vol_cm3']:.1f} cm3", flush=True)
            if T == temps[0] and dg == 0.0:
                figure(cfg, tc, lab, lo, cd, C.out_path(cfg, "feeder_sim.png"))
    ok = all(c["unfed_mm3"] == 0 and c["neck_vs_arm"] >= cfg.get("criteria", {}).get("neck_vs_arm", 1.10)
             and c["riser_vs_neck"] >= cfg.get("criteria", {}).get("riser_vs_neck", 1.30) for c in out["cases"])
    out["pass"] = ok; print("PASS" if ok else "FAIL - enlarge riser / neck or move the neck", "(criteria: unfed 0, neck/arm >= 1.10, riser/neck >= 1.30)")
    C.save_json(cfg, "feeder_sim.json" if not a.sweep else "feeder_sweep.json", out)
