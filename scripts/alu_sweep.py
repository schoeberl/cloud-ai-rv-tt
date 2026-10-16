#!/usr/bin/env python3
"""Recheck an extracted layout at different clock periods without rerouting it.
Run inside tools/dev. Source run must have completed post-route STA.
"""
import argparse
from pathlib import Path
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('run', type=Path)
p.add_argument('periods', nargs='+', type=float)
p.add_argument('--config', type=Path, default=Path('librelane/alu/config.json'))
args = p.parse_args()
sta = sorted(args.run.glob('*-openroad-stapostpnr'), key=lambda x:int(x.name.split('-')[0]))
if not sta:
    p.error('Source run needs completed post-route STA')
if any(t <= 0 for t in args.periods):
    p.error('Periods must be positive')
state = (sta[-1]/'state_out.json').resolve()
config = args.config.resolve()
for period in args.periods:
    tag = f'{config.parent.name}-sta-{period:g}ns'.replace('.', 'p')
    log = Path('build')/f'{tag}.log'
    command = ['librelane', '--from', 'OpenROAD.STAPostPNR', '--to', 'OpenROAD.STAPostPNR',
               '--with-initial-state', str(state), '--override-config', f'CLOCK_PERIOD={period}',
               '--run-tag', tag, str(config)]
    print(f'Rechecking layout at {period:g} ns; log: {log}', flush=True)
    with log.open('w') as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True)
    subprocess.run([sys.executable, 'scripts/alu_timing.py', str(config.parent/'runs'/tag),
                    '--output', str(Path('build')/f'{tag}.json')], check=True)
