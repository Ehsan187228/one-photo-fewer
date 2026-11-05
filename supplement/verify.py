#!/usr/bin/env python3
"""Check the covering designs behind the paper "One Photo Fewer".

Needs Python 3.9 or later and nothing else: no network, no model, no Oris.

    python3 verify.py --self-test    test the checker on good and broken designs
    python3 verify.py                check the three headline records (under a second)
    python3 verify.py --all          check all 29 records (about a minute and a half)

A (v,k,t) covering design is a list of k-element subsets ("blocks") of the
points 1..v such that every t-element subset of the points lies inside at least
one block. This program checks that exactly, in two unrelated ways, and refuses
a design if anything is off.
"""
import argparse
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HEADLINE = {(41, 9, 3), (44, 11, 3), (42, 12, 3)}


def read_structure(design):
    """Return (v, k, t, blocks as sorted tuples) or raise ValueError."""
    for key in ("v", "k", "t", "claimed_size"):
        if type(design.get(key)) is not int:
            raise ValueError(key + " must be a whole number")
    v, k, t, size = design["v"], design["k"], design["t"], design["claimed_size"]
    if not 1 <= t <= k <= v:
        raise ValueError("impossible parameters")
    blocks = design.get("blocks")
    if not isinstance(blocks, list) or len(blocks) != size or size < 1:
        raise ValueError("block count differs from claimed_size")
    clean = []
    for block in blocks:
        if not isinstance(block, list) or len(block) != k:
            raise ValueError("a block has the wrong size")
        if any(type(p) is not int or not 1 <= p <= v for p in block):
            raise ValueError("a point is outside 1..v")
        if len(set(block)) != k:
            raise ValueError("a point is repeated inside a block")
        clean.append(tuple(sorted(block)))
    if len(set(clean)) != size:
        raise ValueError("two blocks are identical")
    return v, k, t, clean


def uncovered_by_prefix(v, t, blocks):
    """Method 1. Every t-subset is a (t-1)-subset plus one larger point.

    For each (t-1)-subset, record as a bit mask which larger points some block
    adds to it. Then compare with the masks a full covering must have.
    """
    reach = {}
    for block in blocks:
        for i in range(t - 1, len(block)):
            last_bit = 1 << block[i]
            for prefix in itertools.combinations(block[:i], t - 1):
                reach[prefix] = reach.get(prefix, 0) | last_bit
    missing = 0
    for prefix in itertools.combinations(range(1, v + 1), t - 1):
        need = ((1 << (v + 1)) - 1) & ~((1 << (prefix[-1] + 1)) - 1) if prefix else ((1 << (v + 1)) - 2)
        missing += bin(need & ~reach.get(prefix, 0)).count("1")
    return missing


def uncovered_by_incidence(v, t, blocks):
    """Method 2. Walk over all t-subsets, intersecting "which blocks hold this point"."""
    holds = [0] * (v + 1)
    for index, block in enumerate(blocks):
        bit = 1 << index
        for point in block:
            holds[point] |= bit
    everything = (1 << len(blocks)) - 1

    def walk(start, depth, mask):
        missing = 0
        if depth == t - 1:
            for point in range(start, v + 1):
                if not mask & holds[point]:
                    missing += 1
            return missing
        for point in range(start, v - (t - depth - 1) + 1):
            narrowed = mask & holds[point]
            if narrowed:
                missing += walk(point + 1, depth + 1, narrowed)
            else:
                missing += math.comb(v - point, t - depth - 1)
        return missing

    return walk(1, 0, everything)


def check_design(design):
    v, k, t, blocks = read_structure(design)
    first = uncovered_by_prefix(v, t, blocks)
    second = uncovered_by_incidence(v, t, blocks)
    if first != second:
        raise ValueError("the two methods disagree: %d and %d" % (first, second))
    if first:
        raise ValueError("%d required subsets are not covered" % first)
    return {"v": v, "k": k, "t": t, "blocks": len(blocks), "required_subsets": math.comb(v, t),
            "uncovered_method_1": first, "uncovered_method_2": second, "valid": True}


def self_test():
    good = {"v": 7, "k": 3, "t": 2, "claimed_size": 7,
            "blocks": [[1, 2, 3], [1, 4, 5], [1, 6, 7], [2, 4, 6], [2, 5, 7], [3, 4, 7], [3, 5, 6]]}
    assert check_design(good)["valid"]
    bad = []
    for change in (
        lambda d: (d["blocks"].pop(), d.update(claimed_size=6)),   # one block missing
        lambda d: d["blocks"].__setitem__(0, [1, 1, 3]),           # repeated point
        lambda d: d["blocks"].__setitem__(0, [1, 2, 8]),           # point out of range
        lambda d: d.update(claimed_size=8),                        # wrong count
        lambda d: d["blocks"].__setitem__(1, [1, 2, 3]),           # duplicate block
        lambda d: d.update(t=True),                                # not a number
        lambda d: d["blocks"].__setitem__(6, [3, 5, 7]),           # pair {5,6} and {3,6} lost
    ):
        broken = json.loads(json.dumps(good))
        change(broken)
        bad.append(broken)
    for broken in bad:
        try:
            check_design(broken)
        except ValueError:
            continue
        raise AssertionError("a broken design was accepted")
    # The two methods must also agree on how much is missing.
    for t, _k, v, seed_blocks in [(3, 4, 8, [[1, 2, 3, 4], [5, 6, 7, 8], [1, 2, 5, 6]]),
                                 (2, 3, 7, good["blocks"][:4])]:
        blocks = [tuple(sorted(b)) for b in seed_blocks]
        truth = sum(not any(set(s) <= set(b) for b in blocks)
                    for s in itertools.combinations(range(1, v + 1), t))
        assert uncovered_by_prefix(v, t, blocks) == truth
        assert uncovered_by_incidence(v, t, blocks) == truth
    return {"good_design_accepted": 1, "broken_designs_rejected": len(bad), "methods_agree_with_brute_force": True}


def check_manifest():
    manifest = json.loads((ROOT / "MANIFEST.json").read_text())
    for name, digest in manifest["files"].items():
        path = (ROOT / name).resolve()
        if ROOT not in path.parents:
            raise ValueError("unsafe path in manifest: " + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("file changed since the manifest was written: " + name)
    return len(manifest["files"])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--self-test", action="store_true", help="test the checker itself")
    parser.add_argument("--all", action="store_true", help="check all 29 records, not only the three headline ones")
    parser.add_argument("--others", action="store_true", help="also check the valid designs in other_designs/ and the second 167-block design")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2))
        return
    checked_files = check_manifest()
    rows = list(csv.DictReader((ROOT / "records.csv").open(encoding="utf-8")))
    results = []
    for row in rows:
        cell = (int(row["v"]), int(row["k"]), int(row["t"]))
        if not args.all and cell not in HEADLINE:
            continue
        path = ROOT / "certificates" / ("%d_%d_%d.json" % cell)
        result = check_design(json.loads(path.read_text()))
        if (result["v"], result["k"], result["t"]) != cell:
            raise ValueError("parameters disagree with records.csv: %s" % (cell,))
        if result["blocks"] != int(row["new_blocks"]):
            raise ValueError("block count disagrees with records.csv: %s" % (cell,))
        if result["blocks"] >= int(row["bar"]):
            raise ValueError("design is not below its bar: %s" % (cell,))
        result["bar"] = int(row["bar"])
        result["blocks_below_bar"] = int(row["bar"]) - result["blocks"]
        results.append(result)
        print("C(%d,%d,%d) <= %d  valid; bar was %d; %s subsets checked two ways" % (
            cell[0], cell[1], cell[2], result["blocks"], result["bar"], format(result["required_subsets"], ",")))
    seeds = 0
    for path in sorted((ROOT / "seeds").glob("*.json")):
        check_design(json.loads(path.read_text()))
        seeds += 1
    others = 0
    if args.others:
        for path in sorted((ROOT / "other_designs").glob("*.json")) + [ROOT / "data" / "41_9_3_second_solution.json"]:
            result = check_design(json.loads(path.read_text()))
            others += 1
            print("%s  valid; %d blocks" % (path.name, result["blocks"]))
    print(json.dumps({"all_valid": True, "designs_checked": len(results), "public_starting_designs_checked": seeds,
                      "other_designs_checked": others, "files_matching_manifest": checked_files}, indent=2))


if __name__ == "__main__":
    main()
