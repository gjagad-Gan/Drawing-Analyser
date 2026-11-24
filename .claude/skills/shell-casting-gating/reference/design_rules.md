# Design rules and default values (Indo Shell Cast, shell moulding, ductile iron)

All values were used and checked on the first job (rocker lever, DI 65-45-12, 0.217 kg, 750 × 650 plate).
Change them in the job config, not in the scripts.

## Process defaults
| Item | Value | Notes |
|---|---|---|
| Moulding | Horizontal core shooter, horizontal parting, horizontal pour | Vertical pour rejected: ~0.6 m head on bottom cavities → shell wall movement / DI swell, upward feeding through gates, +0.6 kg sprue |
| Plate | 750 × 650, 30 mm edge margin (runner ends may go to 26 mm) | |
| Pattern shrink | ≈ 1.0 % DI in shell | applied at toolroom, CAD stays nominal |
| Filter | CFF 10 ppi, horizontal in a drag print at the sprue base, downward flow | 50 × 50 × 22: ~40 kg / ~4 kg/s DI; 75 × 75 above that - always check supplier datasheet |
| Pouring cup | separate ceramic cup on a sprue boss (Z 50) | metal level ~Z 95 |
| Fill time | ~11 s for ~29 kg (shorter than Dietert ~15.6 s) | limits runner heat loss to far cavities |
| Choke | A = W / (ρ_l · t · Cd · √(2 g H_eff)), Cd 0.75 with filter | sprue top by √H taper |
| Pour temperature (stream / cup) | first mould ≤ 1450 °C, last mould ≥ 1390-1395 °C | from pour_window.py; pour ≤ 8-10 min after Mg treatment, stream inoculation |

## Feeding (Level 0/1 → direct feeding with real blind risers)
| Item | Rule |
|---|---|
| Hot spots | every zone separated from the others by a thinner section (e.g. arms either side of a thinner hub) needs its own neck |
| Neck | modulus ≈ 1.0 × zone modulus; short (5-7 mm); straddles the parting; on an allowed face at the hot-spot X |
| Riser | blind capsule on the runner (metal passes through it → hot riser); modulus ≥ 1.2 × neck; top ≥ 12-14 mm above casting top; Ø4 atmospheric vent through the dome |
| Sharing | castings above the runner rotated 180° about Z and shifted so their necks line up with the lower casting's → one riser feeds the long arm of one and the short arm of the other (shift = x_neck1 + x_neck2) |
| Simulation acceptance | unfed 0; neck/arm ≥ 1.10 (aim ≥ 1.14); riser/neck ≥ 1.30; in nominal AND runner-70 °C-colder cases |
| Not acceptable for Level 0/1 | runner-only feeding with ingates smaller than the arm (pressure-control) - margins collapse with colder runner metal (1.03-1.07) |
| Volume check | liquid contraction ≈ 1.6 % per 100 °C above liquidus (~1150 °C); needed riser efficiency ≤ 11 % (blind riser w/o sleeve gives 14-20 %) |

## Layout / gating
| Item | Value |
|---|---|
| Sand runner/riser ↔ casting | ≥ 5-6 mm (riser ↔ own arm = neck length) |
| Casting ↔ casting along a row | ≥ 15 mm; between rows ≥ 17-19 mm |
| Core prints | 5-6 mm beyond the hub; ≥ 5 mm sand to the neighbour's print |
| Branch runners | round, split at the parting, stepped for constant velocity: Ø16 root → Ø10 at the last riser, Ø10 extension to the plate end |
| Cross runner | Ø22 → Ø16 stepped |
| Cold-metal wells | Ø10 × 25 deep in the drag at every runner end (≥ 3-4 mm sand to the last riser) |
| Gating ratio | strongly unpressurised after the choke (≈ 1 : 2.7 : 7 : 90 choke : cross : branches : necks) - gate velocities ~0.01 m/s |

## Thermal model constants (feeder_sim.py)
DI: T_liquidus 1160, T_solidus(eutectic end) 1120 °C, L 230 kJ/kg, ρ 7000, cp 800, k 32. Shell sand: ρ 1500, cp 1100,
k 0.7 (effusivity ~1100). Mould 50 °C. Feeding cut-off fs = 0.7. Grid 1 mm. In-mould metal at end of fill ≈ cup − 30…50 °C.

## Temperature-loss model (temp_loss.py)
q = ΔT / (1/h + √(πτ)/b), h = 1500 W/m²K (check 800), b = 1100; cup → runner entry −30 °C. Rev B2 result: near 1408 / far 1372 °C at 5 s.
Measures in order of effect: faster fill (design time), pour hotter at start, taper runners, warm shells (~200 °C).

## Shell
| Item | Value |
|---|---|
| Thickness | 12 mm conformal (10-14), set by the core-shooter counter-plate gap - the counter plate MUST follow the pattern (flat back → 50-60 mm at flats) |
| Ribs | 8 wide × 15 high, 2° draft, R3 root; grid ~120 mm (between runner rows + near edges); stiffness ×2.3-2.5 |
| Rim | 25 × 15 all round (clamping flange); clips ≤ 150 mm pitch |
| Hold-down | lift on cope ≈ 100 kgf static (×1.5 during pour) for ~29 kg pour: glue parting around every cavity + steel-shot/sand backing or ≥ 170 kgf weights - thickness alone does not stop the bow |
| Pattern / cure | 230-260 °C, ±10 °C across the plate (multi-zone heating, TC at centre + corners); cure ~60-120 s for 12 mm; strip on a flat carrier, cool flat |
| Sand per cope shot | ~16 kg for 750 × 650 (check machine shot capacity) |
| Draft | runners/risers/wells/sprue are modelled straight - add ≥ 1.5° at the toolroom; casting draft comes from the customer model |
