# Lessons learned (do not repeat)

From the first job (rocker lever, 60-72 cavities, 750 × 650 plate). Each item cost a redesign.

1. **Ask which faces are forbidden before placing any gate or neck.** The first two revisions fed through the +Y face,
   which was the primary datum ZA (machining reference). Map datum targets from the drawing onto the model
   (`analyze_part.py` → `z_asymmetric_features`: small one-sided pads are usually datum targets) and confirm with the user.
2. **Ask the soundness level before choosing a feeding philosophy.** Runner-only (pressure-control) feeding gave a
   good yield (55 %) but feed-path margins of only 2 % - not acceptable for Level 0/1. Use direct feeding with blind risers.
3. **The neck metric**: "hottest neck cell / hottest casting cell" is always ~1.0x because the neck heats the casting
   at the contact. Use neck closing time (max-min path through the neck) vs the arm hot spot away (6-25 mm) from the neck.
4. **Simulate the cold case.** Far cavities get runner metal 40-100 °C colder; test every design with the runner/riser
   metal 70 °C colder than the casting metal.
5. **Yield vs cavities**: changing the feeding face (underside, pairs underside-to-underside) raised the cavity count
   60 → 72 with only +1.6 % yield. Present castings-per-mould alongside yield.
6. **Riser below the neck is dead metal** - raising the riser bottom from Z −18 to −14 saved 10 % riser metal at equal
   riser margin; Ø26 instead of Ø28 failed the cold case (riser/neck 1.30). Trim, then re-simulate.
7. **End-of-runner wells**: check they do not overlap the last riser (first attempt did). Script warns.
8. **Fill time from Dietert alone is too slow for big plates** - the far cavities lose 70-100 °C; design for ~11 s and
   check filter flow rate.
9. **Shell thickness does not stop the bow**: edge-clamped only, even 16 mm bows ~2 mm. Hold-down (glue + backing / weight)
   is the fix; ribs add stiffness.
10. **Core shooter back plate must be contoured** - a flat back doubles sand and cures unevenly.
11. **Cope model booleans**: shapely holes come out CW after `orient()`; do NOT also reverse them for OCC → invalid faces
    that silently delete other bodies in the fuse (riser domes vanished). Check `BRepCheck_Analyzer` on every prism.
12. **Core-print seat top must reach the pocket ceiling** (here up to Z 13), else 0.5-4 mm sand fins remain under the
    hub bosses. Print lengths must leave ≥ 5 mm sand to the neighbouring casting's print (first try overlapped by 1 mm).
13. **Thickness checks on STL meshes give false thin readings** at seams - confirm suspicious points on the exact solid
    (BRepClass3d_SolidClassifier).
14. **Big STEP files**: 60 cavities with exact B-spline casting surfaces → 230-350 MB. Use instanced XCAF assemblies for
    layouts; zip single-solid moulds.
15. Look at every rendered sheet before sending - overlapping labels and missing bodies were caught only by looking.
