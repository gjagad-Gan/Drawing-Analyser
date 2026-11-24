"""Step 8a - Excel calculation workbook (inputs yellow, results blue with LIVE formulas) from the JSON outputs.

python3 report_excel.py job.json        # reads layout.json and, if present, analysis/feeder_sim/feeder_sweep/temp_loss/pour_window/shell/cope_shell .json
"""
import sys, os, json, re
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import castlib as C

cfg = C.load_config(sys.argv[1]); lay = C.read_json(cfg, "layout.json")
def opt(n):
    p = C.out_path(cfg, n)
    return json.load(open(p)) if os.path.exists(p) else None
an, fs, sw, tl, pw, sh, cp = (opt(n) for n in ("analysis.json", "feeder_sim.json", "feeder_sweep.json", "temp_loss.json", "pour_window.json", "shell.json", "cope_shell.json"))
part = cfg["part"]; fd = cfg["feeding"]; PO = cfg.get("pouring", {}); g = lay["gating_breakdown_kg"]
H = Font(bold=True, color="FFFFFF"); HF = PatternFill("solid", fgColor="2C3E50"); INP = PatternFill("solid", fgColor="FFF4CC"); OUT = PatternFill("solid", fgColor="E3EEF7")
thin = Side(style="thin", color="BBBBBB"); B = Border(left=thin, right=thin, top=thin, bottom=thin)
wb = Workbook(); ws = wb.active; ws.title = "Gating calc"
for col, w in zip("ABCD", (52, 16, 9, 70)): ws.column_dimensions[col].width = w
ws["A1"] = f"GATING & FEEDING DESIGN — {cfg.get('job', '')}"; ws["A1"].font = Font(bold=True, size=13)
ws["A2"] = f"{part.get('alloy', '')} | shell mould, {cfg.get('plate', {}).get('x', 750)} × {cfg.get('plate', {}).get('y', 650)} plate, horizontal parting | yellow = input, blue = live formula"
r = 4; names = {}
def section(t):
    global r
    r += 1
    for c in range(1, 5): ws.cell(r, c).fill = HF; ws.cell(r, c).font = H
    ws.cell(r, 1, t); ws.cell(r, 2, "Value"); ws.cell(r, 3, "Unit"); ws.cell(r, 4, "Basis / note"); r += 1
def row(key, label, val, unit="", note="", inp=False, fmt="0.00"):
    global r
    ws.cell(r, 1, label); c = ws.cell(r, 2, val); ws.cell(r, 3, unit); ws.cell(r, 4, note)
    c.fill = INP if inp else OUT; c.number_format = fmt
    for k in range(1, 5): ws.cell(r, k).border = B
    ws.cell(r, 4).alignment = Alignment(wrap_text=True, vertical="top"); names[key] = f"B{r}"; r += 1
f = lambda e: "=" + re.sub(r"\{(\w+)\}", lambda m: names[m.group(1)], e)
Vc = lay["casting_kg"] / part.get("rho_solid", 7.1) * 1000
section("1. CASTING")
row("V", "Casting volume", round(Vc, 3), "cm³", "exact CAD volume", True)
row("rho", "Density solid", part.get("rho_solid", 7.1), "g/cm³", "", True); row("rhoL", "Density liquid", part.get("rho_liquid", 7.0), "g/cm³", "", True)
row("Wc", "Casting weight", f("{V}*{rho}/1000"), "kg", "", fmt="0.000")
if an:
    row("Mc", "Overall modulus V/A", round(an["modulus_mm"], 2), "mm", "", True)
    row("Ms", "Largest zone modulus (feeding design basis)", max(z["modulus_mm"] for z in an["zones_X"]), "mm", "analysis.json zones_X; arm/hub junction adds ~5 %", True)
section("2. FEEDING (blind risers, direct feeding for Level 0/1)")
for i, n in enumerate(fd["necks"], 1):
    row(f"nw{i}", f"Neck {i} width × thickness (X {n['x']}, face Y {n['face_y']})", n["w"], "mm", f"thickness {n['t']} mm (straddles parting)", True)
    row(f"nt{i}", f"Neck {i} thickness", n["t"], "mm", "", True)
    row(f"nm{i}", f"Neck {i} modulus", f(f"{{nw{i}}}*{{nt{i}}}/(2*({{nw{i}}}+{{nt{i}}}))"), "mm", "≈ 1.0 × arm modulus")
row("RD", "Riser diameter", lay["riser"]["D"], "mm", "capsule (hemispherical bottom, dome top)", True)
row("RH", "Riser height", lay["riser"]["z1"] - lay["riser"]["z0"], "mm", f"Z {lay['riser']['z0']} … {lay['riser']['z1']}; top must be above casting top", True)
row("RV", "Riser volume", f("PI()*({RD}/2)^2*({RH}-{RD})/1000+4/3*PI()*({RD}/2)^3/1000"), "cm³")
row("RM", "Riser modulus", f("{RV}/((PI()*{RD}*({RH}-{RD})+4*PI()*({RD}/2)^2)/100)*10"), "mm", "≥ 1.2 × neck modulus")
if fs:
    for c in fs["cases"]:
        row(f"s{int(c['T_gate'])}", f"SIM in-mould {c['T_cast']:.0f}, runner {c['T_gate']:.0f}: unfed | neck/arm | riser/neck",
            f"{c['unfed_mm3']:.0f} | {c['neck_vs_arm']:.2f} | {c['riser_vs_neck']:.2f}", "", "criteria: 0 | ≥1.10 | ≥1.30", True, fmt="@")
section("3. WEIGHTS & YIELD (from 3D layout)")
row("n", "Cavities", lay["cavities"], "", f"{lay['rows']} rows × {lay['pairs_per_row']} pairs", True, fmt="0")
row("Wcast", "Castings per mould", f("{n}*{Wc}"), "kg")
for k, lab_ in (("runners", "Runners + wells"), ("risers", "Risers"), ("necks", "Necks"), ("sprue", "Sprue"), ("cup", "Cup residual"), ("filter_area", "Filter well / chamber / filter metal")):
    row("w_" + k, lab_, round(g[k], 3), "kg", "solid-model volume", True)
row("W", "POURED WEIGHT", f("{Wcast}+" + "+".join("{w_%s}" % k for k in ("runners", "risers", "necks", "sprue", "cup", "filter_area"))), "kg")
row("Y", "YIELD", f("{Wcast}/{W}"), "", "", fmt="0.0%")
section("4. POURING TIME, CHOKE, FILTER")
row("T", "Governing section", PO.get("governing_section_mm", 8.0), "mm", "", True); row("K", "Fluidity factor", PO.get("fluidity_K", 1.0), "", "", True)
row("tD", "Dietert time K(1.41+T/14.59)√W[lb]", f("{K}*(1.41+{T}/14.59)*SQRT({W}*2.2046)"), "s")
row("tR", "Design fill time (shorter than Dietert to limit runner heat loss)", lay["fill_time_s"], "s", "", True)
row("He", "Effective head", round(lay["H_eff_mm"], 1), "mm", "cup level to sprue base minus P²/2C", True)
row("cd", "Discharge coefficient (with filter)", PO.get("discharge_coeff", 0.75), "", "", True)
row("Ac", "Choke area A = W/(ρ t c √2gH)", f("{W}*1000/({rhoL}*{tR}*{cd}*SQRT(2*9810*{He})/10)"), "cm²")
row("Dc", "Choke diameter (pattern)", f("SQRT({Ac}*400/PI())"), "mm")
row("q", "Fill rate", f("{W}/{tR}"), "kg/s")
row("fc", "Filter capacity / rate (supplier)", PO.get("filter_capacity_kg", 40), "kg", f"rate {PO.get('filter_rate_kg_s', 4)} kg/s", True)
row("fr", "Filter rate", PO.get("filter_rate_kg_s", 4), "kg/s", "", True)
row("fok", "Filter check", f('IF(AND({W}<={fc},{q}<={fr}),"OK","BIGGER FILTER")'), "")
def table(title, header, rows_):
    w = wb.create_sheet(title)
    for j, v in enumerate(header, 1):
        c = w.cell(1, j, v); c.fill = HF; c.font = H; c.alignment = Alignment(wrap_text=True)
    for i, rr in enumerate(rows_, 2):
        for j, v in enumerate(rr, 1): w.cell(i, j, v).border = B
    for j in range(len(header)): w.column_dimensions[chr(65 + j)].width = 24 if j else 46
    return w
if sw:
    table("Temperature sweep (sim)", ["In-mould °C", "Runner °C", "Unfed mm³", "Neck/arm", "Riser/neck"],
          [[c["T_cast"], c["T_gate"], c["unfed_mm3"], round(c["neck_vs_arm"], 2), round(c["riser_vs_neck"], 2)] for c in sw["cases"]])
if tl:
    w = table("Temperature at risers", ["Case", "Near @2 s", "Far @2 s", "Near @5 s", "Far @5 s", "Near @10 s", "Far @10 s"],
              [[v["name"]] + [round(v[t][m]) for t in ("2.0", "5.0", "10.0") for m in (0, 1)] for k, v in tl.items() if isinstance(v, dict)])
    w.cell(10, 1, "Per riser, design case, 5 s:");
    for i, (x, y, t) in enumerate(tl["per_riser_5s_design"], 11): w.cell(i, 1, f"X {x:.1f}  Y {y:.1f}"); w.cell(i, 2, round(t))
if pw:
    w = table("Pouring window", ["Cup °C", "Hottest cavity °C", "Farthest @5 s °C", "Farthest @2 s °C", "Liquid contraction %", "Riser efficiency needed", "Verdict"],
              [[x["cup"], x["near"], x["far_5s"], x["far_2s"], x["liquid_contraction_pct"], x["riser_eff_needed"], x["verdict"]] for x in pw["rows"]])
    if pw["window"]["first_mould_max"]:
        w.cell(len(pw["rows"]) + 3, 1, f"WINDOW (stream/cup): first mould ≤ {pw['window']['first_mould_max']} °C, last mould ≥ {pw['window']['last_mould_min']} °C").font = Font(bold=True)
if sh:
    w = table("Shell thickness", ["t mm", "Cope kg", "Handling sag mm", "SF handling", "Bow edges-only mm", "SF edges-only", "Local roof kPa", "Hold-down kgf"],
              [[x["t"], round(x["cope_kg"], 1), round(x["sag_handling_mm"], 2), round(x["SF_handling"], 1), round(x["bow_edges_only_mm"], 1), round(x["SF_edges_only"], 1), round(x["local_roof_kPa"]), round(x["hold_down_kgf"])] for x in sh["rows"]])
    w.cell(8, 1, f"Lift on cope {sh['lift_kgf']:.0f} kgf static, {sh['lift_dyn_kgf']:.0f} kgf with impact. Ribs {sh['ribs']['rib_w']}×{sh['ribs']['rib_h']} @ {sh['ribs']['pitch']}: stiffness ×{sh['ribs']['I_gain']:.2f}.")
    if cp: w.cell(9, 1, f"Cope model: {cp['volume_L']:.2f} L ≈ {cp['sand_kg']:.1f} kg sand per shot; ribs X {cp['ribs_x']} / Y {cp['ribs_y']}")
table("Positions", ["Item", "X", "Y", "Rotated 180°"], [["casting", round(c[0], 2), round(c[1], 2), "yes" if c[2] else "no"] for c in lay["casts"]] +
      [["riser", round(x, 2), round(y, 2), ""] for x, y in lay["risers"]])
p = C.out_path(cfg, "gating_calc.xlsx"); wb.save(p); print("written", p)
