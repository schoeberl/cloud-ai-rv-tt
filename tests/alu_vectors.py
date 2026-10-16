#!/usr/bin/env python3
"""Independent Python RV32I model, pipelined expected outputs and test vectors."""
from pathlib import Path
import random

MASK = (1 << 32) - 1

def signed(x):
    return x if x < (1 << 31) else x - (1 << 32)

def reference(a, b, op, valid):
    shift = b & 31
    if op == 0: result = a + b
    elif op == 1: result = a - b
    elif op == 2: result = a << shift
    elif op == 3: result = int(signed(a) < signed(b))
    elif op == 4: result = int(a < b)
    elif op == 5: result = a ^ b
    elif op == 6: result = a >> shift
    elif op == 7: result = signed(a) >> shift
    elif op == 8: result = a | b
    elif op == 9: result = a & b
    elif op == 10: result = b
    elif op == 11: result = (a + b) & ~1
    else: result = 0
    return result & MASK, int(a == b), int(signed(a) < signed(b)), int(a < b), valid

rng = random.Random(0x52563332)
requests = [(1, 0, 0, 0, 0), (1, MASK, MASK, 15, 1)]
edges = [0, 1, 2, 31, 32, 33, 63, 0x7FFFFFFF, 0x80000000, 0x80000001, 0xFFFFFFFE, MASK]
for op in range(16):
    for a in edges:
        for b in edges:
            requests.append((0, a, b, op, 1))
for n in range(20000):
    requests.append((int(n % 2048 == 0), rng.getrandbits(32), rng.getrandbits(32),
                     rng.randrange(16), int(rng.randrange(5) != 0)))
requests.extend([(0, 0, 0, 0, 0)] * 2)
pending = reference(0, 0, 0, 0)
lines = []
for reset, a, b, op, valid in requests:
    if reset:
        output = (0, 0, 0, 0, 0)
        pending = reference(0, 0, 0, 0)
    else:
        output, pending = pending, reference(a, b, op, valid)
    fields = (reset, a, b, op, valid, *output)
    lines.append(' '.join(f'{v:x}' for v in fields))
Path('build/alu-vectors.hex').write_text('\n'.join(lines) + '\n')
print(f'Generated {len(lines)} cycles: directed edges, all opcodes, random streams, bubbles and reset.')
