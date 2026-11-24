---
name: shell-casting-gating
description: Design and verify the gating system, risers/feeding, multi-cavity plate layout, yield, metal-temperature distribution, pouring-temperature window, shell thickness/ribs and the cope shell-mould CAD model for a casting, starting from its 3D STEP model and 2D drawing. Built for Indo Shell Cast practice - shell moulding on a match plate / horizontal core shooter, horizontal parting, ductile (and grey) iron, ceramic foam filter, Level 0/1 soundness. Use whenever the user supplies a casting model or drawing and asks about gating, runners, risers/feeders, shrinkage, yield, cavity count, pouring temperature, shell thickness, ribs or a mould model.
---

# Shell-mould gating & feeding design

This skill turns a casting STEP model (+ its 2D drawing) into a validated, shop-ready proposal:
feeding design checked by a thermal solidification simulation, a full plate layout with gating, yield and choke,
the metal temperature reaching every cavity, the pouring-temperature window, shell thickness / rib design and a
cope shell CAD model, with an Excel calculation book (live formulas) and a PDF drawing set.

Everything is driven by ONE job config (`templates/job_config.example.json`). Scripts live in `scripts/` and write
into the job's `output_dir`. Read `reference/design_rules.md` (numbers and why) and `reference/lessons_learned.md`
(mistakes already made once) before designing.

## 0. Setup (once per machine / container)
```bash
pip install -r .claude/skills/shell-casting-gating/requirements.txt
```
Run scripts from anywhere: `python3 .claude/skills/shell-casting-gating/scripts/<script>.py <job.json>`.
Use `-I`-safe habits: keep the customer STEP/PDF in their own folder, scripts stay in the skill folder.

## 1. Collect inputs - ASK before designing (AskUserQuestion), never assume
Read the drawing PDF yourself first (title block, material spec, datum targets, notes), then confirm with the user:
1. **Material / grade** (density, liquidus, shrink allowance) and the customer material spec.
2. **Soundness requirement** (e.g. Level 0/1 radiographic/sectioning) - decides direct feeding with real risers.
3. **Faces that must NOT carry a gate or neck**: datum targets (ZA/ZB/ZC…), machining references, functional pads
   (valve pallet, screw bosses, bores), part-number marking area. Ask explicitly - on the first job the gates went
   on the primary datum face and had to be redone.
4. **Plate / tool size** and margin, **moulding machine** (horizontal core shooter / dump box), **pour position**
   (horizontal vs vertical), **filter** type & rating, **cavity target** (default: maximise).
5. **Pouring practice**: ladle size, moulds per ladle, temperature drop first→last mould (typ. 50-60 °C), Mg-treatment
   to pour time, inoculation method.
6. Existing core practice (shell cores, print clearances) if the part has undercuts.

## 2. Part analysis
```bash
python3 scripts/analyze_part.py job.json
```
Gives volume/weight, hot spots (inscribed spheres), zone moduli along X, the draw axis from the built-in draft
(least zero-draft area) and the parting Z from the draft sign change, core volume per draw axis, Z-asymmetric
features (datum pads / cut-outs → map the drawing's datum targets onto the model), and +Y/-Y face profiles.

Then set `orientation.rotations` in the config so that: **draw = Z, parting = Z 0, feeding face = +Y, long axis = X**,
and re-run. Match the drawing views to the model (third-angle: check which side the asymmetric features are on) and
write down where every datum target lies. Identify every isolated hot spot (zones separated by thinner sections each
need their own feed). Decide the core: undercut volume along the chosen draw axis must be cored.

## 3. Feeding design + simulation (iterate until PASS)
Fill `feeding` in the config: one neck per isolated hot spot on an allowed face, at the hot spot X.
Starting values (direct feeding for Level 0/1, see design_rules.md):
neck modulus ≈ 1.0 × zone modulus (w × t / 2(w+t)), neck length 5-7 mm, thickness straddling the parting;
riser modulus ≥ 1.2 × neck (capsule, top ≥ 12-14 mm above the casting top), riser on the runner (hot riser).
```bash
python3 scripts/feeder_sim.py job.json
```
Acceptance (worst arm, nominal AND runner metal 70 °C colder): **unfed = 0, neck/arm ≥ 1.10 (aim 1.14), riser/neck ≥ 1.30**.
Then try to trim: raise the riser bottom (metal below the neck is dead weight), reduce D in 2 mm steps; keep the
smallest riser that still passes both cases. Never judge on "hottest neck cell ÷ hottest casting cell" (meaningless).

## 4. Plate layout, gating, yield
```bash
python3 scripts/layout_paired.py job.json
```
Builds the paired-across-runner layout (castings below the runner unrotated, above it rotated 180° and shifted so their
necks line up and share one riser), stepped cross/branch runners, cold-metal wells, sprue + horizontal CFF, choke for the
design fill time, weights, yield, filter check, one-bay clearance check, `gating_only.step` and an instanced
`layout_assembly.step`. Check: cavities, yield, clearances (runner-casting ≥ 5-6 mm, casting-casting ≥ 15 mm, rows ≥ 17 mm),
filter capacity/rate, warnings (no room for wells). If the feeding face must be the underside, rotate the part 180° about Z
in `orientation` so it becomes +Y (that is how option C was handled).

## 5. Temperature reaching each cavity
```bash
python3 scripts/temp_loss.py job.json
```
Per-riser temperature map and the effect of: fill at design time (vs Dietert), stepped runners, hotter start, warm shells.
Target: farthest cavity within ~45 °C of the nearest at mid-pour. If worse: shorten paths, fill faster, taper runners.

## 6. Pouring window
```bash
python3 scripts/pour_window.py job.json        # add --sim for an in-mould 1300-1450 °C feeding sweep (slow)
```
Window = cup/stream temperature range where farthest cavity ≥ 1320 °C at mid-pour AND hottest cavity ≤ 1420 °C AND
riser efficiency needed ≤ 11 %. Compare with the shop's first→last-mould drop; if the drop is wider, reduce moulds per ladle,
cover/preheat the ladle, or stop and pig.

## 7. Shell thickness, ribs, cope model
```bash
python3 scripts/shell_calc.py job.json
python3 scripts/build_cope.py job.json --bay    # quick check of one bay, look at sections
python3 scripts/build_cope.py job.json          # full cope (~3 min); STEP can be > 200 MB -> zip it
```
Default 12 mm conformal shell, 8 × 15 ribs, 25 × 15 rim; lift on cope must be carried by glue + backing/weights - thickness
alone never stops the bow. Set `shell.core_box` (casting-local) with z_top above the highest pocket ceiling and print lengths
that leave ≥ 5 mm sand to the neighbouring casting's print (script warns). Verify thickness on the exact CAD solid, not only
on an STL (mesh seams give false thin readings).

## 8. Reports and delivery
```bash
python3 scripts/report_excel.py job.json      # gating_calc.xlsx (live formulas) - recalc check: soffice --headless --convert-to xlsx
python3 scripts/report_drawings.py job.json   # gating_layout.pdf
```
Look at every PNG/PDF page before sending (overlapping labels, missing bodies). Deliver PDF, XLSX, assembly STEP,
gating STEP, cope STEP (zipped) with SendUserFile. Summarise: cavities, poured weight, yield, choke, risers, feeding
margins, temperature spread, pouring window, shell spec, and what is assumed / must be confirmed.

## Rules that always apply
* **Confidentiality**: customer drawings/models are confidential - never commit them or derived CAD to git, never publish
  them as artifacts; keep them in the job folder / scratchpad and send files directly.
* The simulation is thermal only (no graphite expansion, no mould-wall movement, no filling). State it, and always
  recommend a sectioned + X-rayed first-off (one corner and one centre casting) before tool release.
* All CAD is nominal casting size - pattern / shell shrink is applied at the toolroom (≈1.0 % for DI in shell).
* When a criterion fails, change the design and re-run - do not relax the criterion silently.
* Re-check every geometric change with the one-bay clearance check and the sections.
