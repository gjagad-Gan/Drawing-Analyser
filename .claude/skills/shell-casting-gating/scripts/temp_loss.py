"""Step 5 - metal temperature reaching every riser (heat lost along the runner path), plus improvement cases.

python3 temp_loss.py job.json            # uses <out>/layout.json

Model (1-D heat balance, per riser): path = filter -> stepped cross runner (along Y) -> stepped branch (along X),
passing through the bases of upstream risers (half their wall wetted). Wall flux into the shell
    q = (T - T_shell) / (1/h + sqrt(pi*tau)/b),  b = shell-sand effusivity, tau = time since the wall was wetted,
drop per segment = q * pi*d*L / (rho*c*Q_seg). It is a comparison tool between layouts / measures, not a fill simulation.
Writes <out>/temp_loss.json and temp_map.png.
"""
import sys, json, math, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
import castlib as C

RHO, CP = 7000.0, 800.0
def build(lay):
    risers = [tuple(r) for r in lay["risers"]]; rows = sorted(set(round(r[1], 2) for r in risers))
    return risers, rows
def path(lay, risers, rows, xr, yc, taper):
    segs = []; bR, bm = lay["branch"]["root_d"] / 1000, lay["branch"]["min_d"] / 1000
    cR, cT = lay["cross"]["root_d"] / 1000, lay["cross"]["tip_d"] / 1000
    rd = lay["riser"]["D"] / 1000; N = len(risers)
    if abs(yc) > 45:
        s = np.sign(yc); rr = sorted([y for y in rows if np.sign(y) == s and abs(y) > 45], key=abs); prev = 0.033
        nmax = sum(1 for r in risers if np.sign(r[1]) == s and abs(r[1]) > 45)
        for y in rr:
            if abs(y) > abs(yc) + 0.1: break
            n = sum(1 for r in risers if np.sign(r[1]) == s and abs(r[1]) >= abs(y) - 0.1)
            dd = max(cT, cR * math.sqrt(n / nmax)) if taper else cR
            segs.append((dd, abs(y) / 1000 - prev, n)); prev = abs(y) / 1000
    s = np.sign(xr); bl = sorted([r for r in risers if abs(r[1] - yc) < 0.1 and np.sign(r[0]) == s], key=lambda r: abs(r[0]))
    prev = 0.033 if abs(yc) < 45 else 0.0
    for i, r in enumerate(bl):
        n = len(bl) - i; dd = max(bm, bR * math.sqrt(n / len(bl))) if taper else bR
        segs.append((dd, max(abs(r[0]) / 1000 - prev - rd / 2, 0.0), n))
        if abs(r[0] - xr) < 0.1: break
        segs.append((rd, rd * 0.5, n)); prev = abs(r[0]) / 1000 + rd / 2
    return segs
def temps(lay, tau, Q_cm3, T_in, T_sh=50.0, h=1500.0, b=1100.0, taper=True):
    risers, rows = build(lay); qr = Q_cm3 * 1e-6 / len(risers); out = []
    for (x, y) in risers:
        T = T_in
        for dd, L, n in path(lay, risers, rows, x, y, taper):
            T -= (T - T_sh) / (1 / h + math.sqrt(math.pi * tau) / b) * math.pi * dd * L / (RHO * CP * qr * max(n, 1))
        out.append(T)
    return risers, out

if __name__ == "__main__":
    cfg = C.load_config(sys.argv[1]); lay = C.read_json(cfg, "layout.json"); PO = cfg.get("pouring", {})
    T_cup = PO.get("T_cup_design", 1440.0); loss_cup = PO.get("cup_to_runner_loss", 30.0)
    Qd = lay["Q_cm3_s"]; Qslow = lay["poured_kg"] * 1000 / 7.0 / lay["dietert_time_s"]
    cases = {"dietert_cold": ("Dietert fill time, no taper, cold shells, pour T_cup-20", dict(Q=Qslow, T_in=T_cup - 20 - loss_cup, T_sh=50.0, taper=False)),
             "fast_fill": ("+ fill at design time (bigger choke)", dict(Q=Qd, T_in=T_cup - 20 - loss_cup, T_sh=50.0, taper=False)),
             "taper": ("+ stepped runners", dict(Q=Qd, T_in=T_cup - 20 - loss_cup, T_sh=50.0, taper=True)),
             "hot": ("+ pour at T_cup_design", dict(Q=Qd, T_in=T_cup - loss_cup, T_sh=50.0, taper=True)),
             "design": ("DESIGN: + shells poured warm (~200 °C)", dict(Q=Qd, T_in=T_cup - loss_cup, T_sh=200.0, taper=True)),
             "design_lowh": ("design, low contact coefficient h=800", dict(Q=Qd, T_in=T_cup - loss_cup, T_sh=200.0, taper=True, h=800.0))}
    R = {}
    for k, (nm, kw) in cases.items():
        R[k] = dict(name=nm, **{str(t): [max(temps(lay, t, kw["Q"], kw["T_in"], kw["T_sh"], kw.get("h", 1500.0), taper=kw["taper"])[1]),
                                         min(temps(lay, t, kw["Q"], kw["T_in"], kw["T_sh"], kw.get("h", 1500.0), taper=kw["taper"])[1])] for t in (2.0, 5.0, 10.0)})
        print(f"{nm:58s} 5 s: near {R[k]['5.0'][0]:.0f} far {R[k]['5.0'][1]:.0f} spread {R[k]['5.0'][0]-R[k]['5.0'][1]:.0f} °C")
    kw = cases["design"][1]; risers, T5 = temps(lay, 5.0, kw["Q"], kw["T_in"], kw["T_sh"], taper=True)
    R["per_riser_5s_design"] = [[x, y, t] for (x, y), t in zip(risers, T5)]
    C.save_json(cfg, "temp_loss.json", R)
    fig, axs = plt.subplots(1, 2, figsize=(16, 7))
    for ax, (k, tau) in zip(axs, (("dietert_cold", 5.0), ("design", 5.0))):
        kw = cases[k][1]; rs, T = temps(lay, tau, kw["Q"], kw["T_in"], kw["T_sh"], taper=kw["taper"])
        sc = ax.scatter([r[0] for r in rs], [r[1] for r in rs], c=T, cmap="coolwarm", vmin=min(T) - 5, vmax=T_cup - loss_cup, s=150, edgecolor="k")
        for (x, y), t in zip(rs, T): ax.text(x, y + 14, f"{t:.0f}", fontsize=6, ha="center")
        ax.set_aspect("equal"); ax.set_title(f"{cases[k][0]} — {tau:.0f} s into the pour", fontsize=9, loc="left")
        plt.colorbar(sc, ax=ax, shrink=0.7, label="°C arriving at riser")
    plt.tight_layout(); plt.savefig(C.out_path(cfg, "temp_map.png"), dpi=95)
