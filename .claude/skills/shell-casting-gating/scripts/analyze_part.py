"""Step 1 - geometry analysis of a casting STEP model.

python3 analyze_part.py job.json

Writes <out>/analysis.json and PNGs: views, thickness/hot-spot map, sections, draft & core maps.
Reports: volume / weight / area / bbox, overall modulus, hot spots (inscribed spheres), section-modulus
profile and zone moduli along X, draw direction from built-in draft, parting Z from the draft sign change,
core (undercut) volume per draw direction, +Z/-Z asymmetric features (datum pads, cut-outs), and the +Y / -Y
face profiles that candidate feeding faces would sit on.
"""
import sys, json, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import ndimage
import castlib as C

cfg = C.load_config(sys.argv[1])
rho = cfg["part"].get("rho_solid", 7.1)
S = C.load_part(cfg)
V = C.vol(S); A = C.area(S); lo, hi = C.bbox(S)
F, fo, fp = C.fine_voxels(cfg)
res = dict(volume_cm3=V / 1000, area_cm2=A / 100, weight_kg=V * rho / 1e6, modulus_mm=V / A,
           bbox_min=lo.tolist(), bbox_max=hi.tolist(), size_mm=(hi - lo).tolist())
print(f"V {V/1000:.2f} cm3, A {A/100:.1f} cm2, weight {V*rho/1e6:.3f} kg, overall modulus {V/A:.2f} mm, size {np.round(hi-lo,1)}")

# ---------------- hot spots (inscribed-sphere radius field) ----------------
D = ndimage.distance_transform_edt(F) * fp
mx = ndimage.maximum_filter(D, size=int(6 / fp))
pk = np.argwhere((D == mx) & (D > 2.5))
pts = sorted([(float(D[tuple(i)]), (fo + i * fp).tolist()) for i in pk], key=lambda t: -t[0])
spots = []
for r, c in pts:
    if all(np.linalg.norm(np.array(c) - np.array(s["at"])) > 6 for s in spots):
        spots.append(dict(R=round(r, 2), dia=round(2 * r, 1), at=[round(x, 1) for x in c]))
res["hot_spots"] = spots[:15]
print("hot spots (inscribed dia, location):", [(s["dia"], s["at"]) for s in spots[:8]])

# ---------------- section modulus profile along X and zone moduli ----------------
import trimesh
m = trimesh.load(C.out_path(cfg, "part_oriented.stl")); m.merge_vertices()
xs = fo[0] + np.arange(F.shape[0]) * fp
prof = []
for x in np.arange(lo[0] + 1.5, hi[0] - 1.0, 1.5):
    s = C.thin(F, fo, fp, 0, x); ar = s.sum() * fp * fp
    per = (s ^ ndimage.binary_erosion(s)).sum() * fp
    prof.append((float(x), float(ar), float(ar / max(per, 1e-6)), float(D[int(round((x - fo[0]) / fp))].max())))
prof = np.array(prof)
res["section_profile_X"] = prof.round(2).tolist()
# zones: split at local minima of the inscribed-radius profile
rr = ndimage.uniform_filter1d(prof[:, 3], 3)
mins = [i for i in range(2, len(rr) - 2) if rr[i] < rr[i - 1] and rr[i] <= rr[i + 1] and rr[i] < 0.75 * max(rr[:i].max(), rr[i:].max())]
cuts = [lo[0] - 1] + [prof[i, 0] for i in mins] + [hi[0] + 1]
c = m.triangles_center; Af = m.area_faces
zones = []
scale = V / (F.sum() * fp ** 3)
for a, b in zip(cuts[:-1], cuts[1:]):
    sel = (xs >= a) & (xs < b); Vz = F[sel].sum() * fp ** 3 * scale
    Az = Af[(c[:, 0] >= a) & (c[:, 0] < b)].sum()
    if Vz > 0.02 * V:
        zones.append(dict(x_from=round(float(a), 1), x_to=round(float(b), 1), V_cm3=round(Vz / 1000, 2), modulus_mm=round(Vz / Az, 2),
                          max_inscribed_dia=round(2 * float(D[sel].max()), 1)))
res["zones_X"] = zones
print("zones along X:", [(z["x_from"], z["x_to"], z["modulus_mm"]) for z in zones])

# ---------------- draw direction from built-in draft, parting from draft sign change ----------------
n = m.face_normals
draft = {}
for name, d in (("X", (1, 0, 0)), ("Y", (0, 1, 0)), ("Z", (0, 0, 1))):
    ang = np.degrees(np.arcsin(np.clip(np.abs(n @ np.array(d)), 0, 1)))
    draft[name] = dict(zero_lt_0p3=float(Af[ang < 0.3].sum()), d0p3_1=float(Af[(ang >= 0.3) & (ang < 1)].sum()),
                       d1_3=float(Af[(ang >= 1) & (ang < 3)].sum()), d3_10=float(Af[(ang >= 3) & (ang < 10)].sum()))
res["draft_area_mm2"] = draft
best = min(draft, key=lambda k: draft[k]["zero_lt_0p3"])
res["suggested_draw_axis"] = best
side = (np.abs(n[:, 2]) < 0.12) & (np.abs(n[:, 2]) > 0.005) & (np.hypot(c[:, 0], c[:, 1]) > 0)
bins = np.arange(np.floor(lo[2]), np.ceil(hi[2]) + 2, 2.0)
up = np.histogram(c[side & (n[:, 2] > 0), 2], bins, weights=Af[side & (n[:, 2] > 0)])[0]
dn = np.histogram(c[side & (n[:, 2] < 0), 2], bins, weights=Af[side & (n[:, 2] < 0)])[0]
k = int(np.argmin(np.abs(np.cumsum(up) - np.cumsum(dn)[-1] + np.cumsum(dn))))
cross = [float(bins[i + 1]) for i in range(len(up) - 1) if dn[i] > up[i] and up[i + 1] > dn[i + 1]]
res["parting_Z_from_draft"] = cross[0] if cross else None
print(f"draw axis with least zero-draft area: {best}; draft sign change (parting) at Z ~ {res['parting_Z_from_draft']}")

# ---------------- core (undercut) volume per draw direction ----------------
core = {}
fig, axs = plt.subplots(1, 3, figsize=(18, 5))
for ax in range(3):
    Aax = np.moveaxis(F, ax, -1); cs = np.cumsum(Aax, -1); tot = cs[..., -1:]
    gap = (~Aax) & (cs > 0) & (cs < tot); gap = ndimage.binary_opening(gap, iterations=1)
    G = np.moveaxis(gap, -1, ax); core["XYZ"[ax]] = float(G.sum() * fp ** 3 / 1000)
    pa = 2 if ax != 2 else 1; rest = [i for i in range(3) if i != pa]
    ext = [fo[rest[0]], fo[rest[0]] + F.shape[rest[0]] * fp, fo[rest[1]], fo[rest[1]] + F.shape[rest[1]] * fp]
    axs[ax].imshow(F.max(pa).T, origin="lower", extent=ext, cmap="Greys", alpha=.4)
    axs[ax].imshow(np.ma.masked_equal(G.sum(pa).T, 0), origin="lower", extent=ext, cmap="autumn")
    axs[ax].set_title(f"draw along {'XYZ'[ax]}: core needed {core['XYZ'[ax]]:.1f} cm3")
plt.tight_layout(); plt.savefig(C.out_path(cfg, "core_need.png"), dpi=70); plt.close()
res["core_volume_cm3_by_draw_axis"] = core
print("core (undercut) volume by draw axis cm3:", core)

# ---------------- Z-mirror asymmetry (datum pads, cut-outs on one side only) ----------------
zc = -fo[2] / fp; idx = np.arange(F.shape[2]); mir = np.round(2 * zc - idx).astype(int); ok = (mir >= 0) & (mir < F.shape[2])
Fm = np.zeros_like(F); Fm[:, :, ok] = F[:, :, mir[ok]]
diff = F & ~Fm; lab, nn = ndimage.label(diff)
sz = ndimage.sum(diff, lab, range(1, nn + 1)) * fp ** 3
feat = []
for i in np.argsort(-sz)[:10]:
    if sz[i] < 3: break
    cc = np.array(ndimage.center_of_mass(diff, lab, i + 1)) * fp + fo
    feat.append(dict(mm3=round(float(sz[i]), 1), at=[round(x, 1) for x in cc]))
res["z_asymmetric_features"] = feat
print("material present on one Z side only (pads / cut-outs on the other):", [(f["mm3"], f["at"]) for f in feat[:6]])

# ---------------- +Y / -Y face profiles (candidate feeding faces) ----------------
band = np.abs(fo[2] + np.arange(F.shape[2]) * fp) <= 7.5
fp_prof = []
for x in np.arange(lo[0] + 2, hi[0] - 1, 3.0):
    s = C.thin(F, fo, fp, 0, x)[:, band]; ys = np.where(s.any(1))[0]
    if len(ys): fp_prof.append((round(float(x), 1), round(float(fo[1] + ys.max() * fp), 1), round(float(fo[1] + ys.min() * fp), 1)))
res["face_profile_X_ymax_ymin"] = fp_prof

# ---------------- pictures ----------------
fig, axs = plt.subplots(1, 3, figsize=(18, 5))
for i, (pa, lab_) in enumerate(((2, "plan (along Z)"), (1, "along Y"), (0, "along X"))):
    rest = [a for a in range(3) if a != pa]
    ext = [fo[rest[0]], fo[rest[0]] + F.shape[rest[0]] * fp, fo[rest[1]], fo[rest[1]] + F.shape[rest[1]] * fp]
    im = axs[i].imshow((D.max(axis=pa) * 2).T, origin="lower", extent=ext, cmap="inferno")
    axs[i].set_title("max section thickness (2R, mm), " + lab_); plt.colorbar(im, ax=axs[i])
for s in spots[:6]:
    axs[0].plot(s["at"][0], s["at"][1], "c+", ms=10)
plt.tight_layout(); plt.savefig(C.out_path(cfg, "hot_spots.png"), dpi=70); plt.close()
fig, axs = plt.subplots(1, 2, figsize=(16, 4))
axs[0].plot(prof[:, 0], prof[:, 2], label="2-D section modulus A/P (mm)"); axs[0].plot(prof[:, 0], prof[:, 3], label="max inscribed radius (mm)")
for x in cuts[1:-1]: axs[0].axvline(x, color="k", ls=":")
axs[0].legend(); axs[0].set_xlabel("X mm"); axs[0].set_title("thickness profile along X (dotted = zone cuts)")
axs[1].plot([p[0] for p in fp_prof], [p[1] for p in fp_prof], label="+Y face (max Y, |Z|<=7.5)")
axs[1].plot([p[0] for p in fp_prof], [p[2] for p in fp_prof], label="-Y face (min Y, |Z|<=7.5)")
axs[1].legend(); axs[1].set_title("candidate feeding faces"); axs[1].set_xlabel("X mm")
plt.tight_layout(); plt.savefig(C.out_path(cfg, "profiles.png"), dpi=70); plt.close()
C.save_json(cfg, "analysis.json", res)
print("written", C.out_path(cfg, "analysis.json"))
