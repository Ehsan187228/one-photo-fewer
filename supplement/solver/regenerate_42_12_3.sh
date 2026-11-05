#!/bin/sh
# Regenerate the 74-block (42,12,3) record from its public 75-block starting design.
# Needs a C compiler and Python 3. Takes about half a minute on a laptop.
set -e
here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cc -O2 -o "$work/cover_det" "$here/cover_det.c" -lm
"$work/cover_det" 42 12 3 74 shrink "$here/seed_42_12_3.txt" 900 0.9 512 "$work/solution.txt" 150000000 | tail -1
python3 -I -B - "$work/solution.txt" "$here/../certificates/42_12_3.json" <<'PY'
import json, sys
rows = [line.split() for line in open(sys.argv[1]) if line.strip()]
found = {frozenset(map(int, r)) for r in rows[1:]}
paper = {frozenset(b) for b in json.load(open(sys.argv[2]))["blocks"]}
print("same 74 blocks as the certificate:", found == paper)
sys.exit(0 if found == paper else 1)
PY
