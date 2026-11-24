"""Step 6 - pouring-temperature window (temperature in the stream / pouring cup, first and last mould of a ladle).

python3 pour_window.py job.json [--sim]

Lower limit: the farthest cavity must receive metal >= criteria.far_cavity_min_C (default 1320 °C) at mid-pour
             (cold laps / misruns / dross / carbides in thin tips below that).
Upper limit: hottest cavity in-mould temperature <= criteria.near_cavity_max_C (default 1420 °C) AND the riser feed
             efficiency needed (liquid contraction of casting share + necks + riser itself / riser volume) <= criteria.feed_eff_max
             (default 0.11; blind riser without sleeve delivers ~0.14-0.20). Above it: more feed demand, longer liquid time,
             shell softening / mould-wall movement -> DI shrinkage, burn-on.
--sim additionally runs feeder_sim at in-mould 1300..1450 (nominal and cold runner) to confirm the feeding order holds.
Writes <out>/pour_window.json.
"""
import sys, json, argparse, numpy as np
import castlib as C
from temp_loss import temps

ap = argparse.ArgumentParser(); ap.add_argument("job"); ap.add_argument("--sim", action="store_true"); a = ap.parse_args()
cfg = C.load_config(a.job); lay = C.read_json(cfg, "layout.json"); PO = cfg.get("pouring", {}); CR = cfg.get("criteria", {})
far_min = CR.get("far_cavity_min_C", 1320.0); near_max = CR.get("near_cavity_max_C", 1420.0); eff_max = CR.get("feed_eff_max", 0.11)
loss = PO.get("cup_to_runner_loss", 30.0); TL = cfg["part"].get("T_liquidus", 1150.0); kc = CR.get("liquid_contraction_pct_per_100C", 1.6)
Vc = C.vol(C.load_part(cfg)) / 1000; Vr = lay["riser_vol_cm3"]
necks = cfg["feeding"]["necks"]; Vn = sum(n["w"] * n["t"] * cfg["feeding"].get("neck_gap", 5.0) for n in necks) / 1000
rows = []
for cup in range(1360, 1481, 5):
    rs, T5 = temps(lay, 5.0, lay["Q_cm3_s"], cup - loss, 200.0); _, T2 = temps(lay, 2.0, lay["Q_cm3_s"], cup - loss, 200.0)
    near, far5, far2 = max(T5), min(T5), min(T2)
    f = max(near - TL, 0) * kc / 100 / 100
    eff = (Vc * len(lay["casts"]) / len(lay["risers"]) + Vn + Vr) * f / Vr
    verdict = "TOO COLD" if far5 < far_min else ("TOO HOT" if (near > near_max or eff > eff_max) else "OK")
    rows.append(dict(cup=cup, near=round(near), far_5s=round(far5), far_2s=round(far2), liquid_contraction_pct=round(f * 100, 2), riser_eff_needed=round(eff, 3), verdict=verdict))
ok = [r["cup"] for r in rows if r["verdict"] == "OK"]
win = dict(last_mould_min=min(ok) if ok else None, first_mould_max=max(ok) if ok else None)
print(f"{'cup':>5} {'near':>5} {'far5s':>6} {'far2s':>6} {'LC%':>5} {'eff':>6}  verdict")
for r in rows: print(f"{r['cup']:5d} {r['near']:5d} {r['far_5s']:6d} {r['far_2s']:6d} {r['liquid_contraction_pct']:5.1f} {r['riser_eff_needed']:6.3f}  {r['verdict']}")
if ok:
    print(f"\nWINDOW (stream / cup): first mould <= {win['first_mould_max']} °C, last mould >= {win['last_mould_min']} °C  -> {win['first_mould_max']-win['last_mould_min']} °C")
    drop = PO.get("ladle_drop_C")
    if drop and drop > win["first_mould_max"] - win["last_mould_min"]:
        print(f"WARNING: ladle drop {drop} °C is wider than the window - fewer moulds per ladle / covered, preheated ladle / stop and pig")
else:
    print("NO WINDOW - shorten runner paths, fill faster, enlarge risers, or warm the shells")
out = dict(rows=rows, window=win)
if a.sim:
    import feeder_sim as FS
    P = dict(FS.DEF, **cfg.get("simulation", {})); sims = []
    for T in (1300, 1360, 1420, 1450):
        for dg in (0.0, -45.0):
            r, _ = FS.run_case(cfg, P, float(T), float(T + dg)); sims.append(r)
            print(f"sim in-mould {T} gating {dg:+.0f}: unfed {r['unfed_mm3']:.0f} neck/arm {r['neck_vs_arm']:.2f} riser/neck {r['riser_vs_neck']:.2f}", flush=True)
    out["sim_sweep"] = sims
C.save_json(cfg, "pour_window.json", out)
