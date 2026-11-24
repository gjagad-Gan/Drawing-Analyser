#!/usr/bin/env bash
# Runs the whole pipeline for one job config. Usage: run_all.sh job.json [--with-cope]
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"; J="$1"
python3 "$D/analyze_part.py" "$J"
python3 "$D/feeder_sim.py" "$J"
python3 "$D/layout_paired.py" "$J"
python3 "$D/temp_loss.py" "$J"
python3 "$D/pour_window.py" "$J"
python3 "$D/shell_calc.py" "$J"
if [[ "${2:-}" == "--with-cope" ]]; then python3 "$D/build_cope.py" "$J"; fi
python3 "$D/report_excel.py" "$J"
python3 "$D/report_drawings.py" "$J"
