#!/usr/bin/env python3
"""Extract register-to-register timing from LibreLane post-route STA reports.

Tmin = constrained period - worst register-to-register setup slack. This includes
clock skew, cell setup time, extracted interconnect and the SDC uncertainty.
I/O paths are deliberately excluded. Recheck the estimated period with STA.
"""
import argparse
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('run', type=Path)
parser.add_argument('--output', type=Path, default=Path('build/alu-timing.json'))
args = parser.parse_args()
steps = sorted(args.run.glob('*-openroad-stapostpnr'), key=lambda p: int(p.name.split('-')[0]))
if not steps:
    parser.error('No post-route STA step found')
sta = steps[-1]

def register_paths(report):
    paths = []
    for block in report.read_text().split('Startpoint:')[1:]:
        start = block.splitlines()[0].strip()
        end = re.search(r'^Endpoint:\s*(.*)', block, re.M)
        slack = re.search(r'([-+\d.eE]+)\s+slack \((?:MET|VIOLATED)\)', block)
        if end and slack and 'flip-flop' in start and 'flip-flop' in end.group(1):
            paths.append(dict(startpoint=start, endpoint=end.group(1).strip(), slack_ns=float(slack.group(1))))
    if not paths:
        raise RuntimeError(f'No register-to-register paths in {report}')
    return paths

corners = []
print('Corner                     Period(ns)  Reg slack(ns)  Tmin(ns)  Fmax(MHz)  Hold(ns)')
for corner in sorted(sta.iterdir()):
    if not corner.is_dir() or not (corner / 'max.rpt').exists():
        continue
    period = float(re.search(r'^Period:\s*([\d.]+)', (corner/'clock.rpt').read_text(), re.M).group(1))
    setup = min(register_paths(corner/'max.rpt'), key=lambda p:p['slack_ns'])
    hold = min(register_paths(corner/'min.rpt'), key=lambda p:p['slack_ns'])
    tmin = period - setup['slack_ns']
    row = dict(corner=corner.name, period_ns=period, reg_setup_slack_ns=setup['slack_ns'],
               estimated_min_period_ns=tmin, estimated_fmax_mhz=1000/tmin,
               reg_hold_slack_ns=hold['slack_ns'], critical_path=setup,
               report=str(corner/'max.rpt'))
    corners.append(row)
    print(f'{corner.name:26s} {period:9.3f} {setup["slack_ns"]:14.6f} {tmin:9.6f} {1000/tmin:10.3f} {hold["slack_ns"]:9.6f}')
worst = max(corners, key=lambda r:r['estimated_min_period_ns'])
summary = dict(run=str(args.run), method='period minus worst register-to-register setup slack',
               worst_corner=worst, corners=corners)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(summary, indent=2)+'\n')
print(f'Worst corner: {worst["corner"]}, estimated Fmax {worst["estimated_fmax_mhz"]:.3f} MHz')
print(f'Wrote {args.output}')
