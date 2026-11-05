#!/usr/bin/env python3
"""Recheck the structural claims made in the paper "One Photo Fewer".

Needs Python 3.9 or later and nothing else. Run:  python3 check_structure.py

It checks seven things, printing what it finds and stopping if a claim fails:

  1. The (41,9,3) designs split into a 25-point and a 16-point part that carry the
     affine planes AG(2,5) and AG(2,4). Exactly 100 blocks are "a line of one plus a
     line of the other", and those 100 are identical in the public design, in the new
     record, and in a second 167-block solution from rerunning the same command, which shares nothing else.
  2. The (44,11,3) designs split into two planes of order 4 and a third with one line
     removed, and 64 blocks of the form line + line + (line minus a point) are identical
     in the public design and in the record.
  3. Each headline record is tight: removing any one block breaks coverage. At the public starting
     design, removing the weakest block leaves 6, 9 and 7 triples uncovered, and exactly one
     single-point swap out of tens of thousands then helps.
  4. The (42,12,3) record has new twin points, and three 74-block solutions share no block.
  5. The stuck (48,23,3) state with 15 blocks is one triple short for a counting reason:
     it is built on the geometry PG(3,2), and every block is exactly full.
  6. Proposition 1 of the paper's appendix, by building that object from scratch.
  7. Proposition 2, by trying all 817,190 ways to place the spare seats.
"""
import collections
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GF4_MUL = [[0, 0, 0, 0], [0, 1, 2, 3], [0, 2, 3, 1], [0, 3, 1, 2]]


def load(folder, name):
    return [frozenset(b) for b in json.loads((ROOT / folder / name).read_text())["blocks"]]


def lines_ag25(grid):
    lines = [frozenset(grid[x][y] for y in range(5)) for x in range(5)]
    lines += [frozenset(grid[x][(m * x + c) % 5] for x in range(5)) for m in range(5) for c in range(5)]
    return lines


def lines_ag24(grid):
    lines = [frozenset(grid[x][y] for y in range(4)) for x in range(4)]
    lines += [frozenset(grid[x][GF4_MUL[m][x] ^ c] for x in range(4)) for m in range(4) for c in range(4)]
    return lines


def core_41(blocks, part_a, part_b, lines_a, lines_b):
    return {b for b in blocks if b & part_a in lines_a and b & part_b in lines_b}


def check_41(structure):
    grid_a, grid_b = structure["A_grid_GF5"], structure["B_grid_GF4"]
    part_a, part_b = set(sum(grid_a, [])), set(sum(grid_b, []))
    assert len(part_a) == 25 and len(part_b) == 16 and len(part_a | part_b) == 41
    lines_a, lines_b = set(lines_ag25(grid_a)), set(lines_ag24(grid_b))
    assert len(lines_a) == 30 and len(lines_b) == 20
    for lines, points, per_pair in ((lines_a, part_a, 1), (lines_b, part_b, 1)):
        for pair in itertools.combinations(sorted(points), 2):
            assert sum(set(pair) <= line for line in lines) == per_pair
    seed, final, other = load("seeds", "41_9_3.json"), load("certificates", "41_9_3.json"), load("data", "41_9_3_second_solution.json")
    core_seed = core_41(seed, part_a, part_b, lines_a, lines_b)
    core_final = core_41(final, part_a, part_b, lines_a, lines_b)
    core_other = core_41(other, part_a, part_b, lines_a, lines_b)
    assert len(core_final) == 100 and core_seed == core_final == core_other
    assert set(final) & set(other) == core_final
    assert len(set(seed) & set(final)) == 109
    only_b = lambda blocks: sum(b <= part_b for b in blocks)
    assert (only_b(seed), only_b(final), only_b(other)) == (10, 9, 9)
    print("(41,9,3): 25 + 16 points carry AG(2,5) and AG(2,4). The same 100 line-plus-line blocks appear in the")
    print("          public design, the record and the second solution. Record and second solution share nothing else.")
    print("          Blocks inside the 16-point part: public %d, record %d, second solution %d." % (only_b(seed), only_b(final), only_b(other)))


def check_44(structure):
    labels = {int(k): v for k, v in structure["points"].items()}
    parts = {name: {p for p, (part, _) in labels.items() if part == name} for name in ("P1", "P2", "Q")}
    assert [len(parts[n]) for n in ("P1", "P2", "Q")] == [16, 16, 12]
    vector = {p: vec for p, (_, vec) in labels.items()}

    def xor_all(points):
        out = 0
        for p in points:
            out ^= vector[p]
        return out

    def is_flat(points):
        return len(points) == 4 and xor_all(points) == 0

    deleted = set(range(16)) - {vector[p] for p in parts["Q"]}
    assert len(deleted) == 4
    differences = lambda values: {a ^ b for a, b in itertools.combinations(values, 2)}
    deleted_direction = differences(deleted)

    def core(blocks):
        found = set()
        for b in blocks:
            p1, p2, q = b & parts["P1"], b & parts["P2"], b & parts["Q"]
            if len(q) != 3 or not is_flat(p1) or not is_flat(p2):
                continue
            direction = differences(vector[p] for p in p1)
            if direction != differences(vector[p] for p in p2) or direction == deleted_direction:
                continue
            # The third line is what the two given lines add up to; it has lost exactly one point.
            offset = vector[next(iter(p1))] ^ vector[next(iter(p2))]
            third_line = {offset} | {offset ^ d for d in direction}
            if {vector[p] for p in q} == third_line - deleted:
                found.add(b)
        return found

    seed, final = load("seeds", "44_11_3.json"), load("certificates", "44_11_3.json")
    core_seed, core_final = core(seed), core(final)
    assert len(core_final) == 64 and core_seed == core_final
    directions = {frozenset(differences(vector[p] for p in b & parts["P1"])) for b in core_final} | {frozenset(deleted_direction)}
    assert len(directions) == 5 and set().union(*directions) == set(range(1, 16))  # a spread: the five directions of a plane of order 4
    assert all(sum(p in b for b in core_final) == 16 for p in range(1, 45))
    print("(44,11,3): 16 + 16 + 12 points. The same 64 line + line + (line minus a point) blocks appear in the public")
    print("           design and the record. Every one of the 44 points lies in exactly 16 of them.")


def weakest_and_swaps(blocks):
    count = collections.Counter(s for b in blocks for s in itertools.combinations(sorted(b), 3))
    private = {b: sum(count[s] == 1 for s in itertools.combinations(sorted(b), 3)) for b in blocks}
    return count, private


def check_tightness():
    expected = {(41, 9): (6, 19, 48096), (44, 11): (9, 12, 39567), (42, 12): (7, 44, 26640)}
    for (v, k), (seed_gap, final_gap, swaps) in expected.items():
        name = "%d_%d_3.json" % (v, k)
        seed, final = load("seeds", name), load("certificates", name)
        _, private_seed = weakest_and_swaps(seed)
        _, private_final = weakest_and_swaps(final)
        assert min(private_seed.values()) == seed_gap and min(private_final.values()) == final_gap
        assert all(n > 0 for n in private_final.values())
        # Remove the weakest block of the public design and count helpful one-point swaps.
        weakest = min(seed, key=lambda b: private_seed[b])
        rest = [b for b in seed if b != weakest]
        count, _ = weakest_and_swaps(rest)
        holes = {s for s in itertools.combinations(range(1, v + 1), 3) if count[s] == 0}
        assert len(holes) == seed_gap
        helpful = 0
        total = 0
        for b in rest:
            members = sorted(b)
            for out in members:
                kept = [p for p in members if p != out]
                lost = sum(count[tuple(sorted((out, x, y)))] == 1 for x, y in itertools.combinations(kept, 2))
                for new in range(1, v + 1):
                    if new in b:
                        continue
                    total += 1
                    gained = sum(tuple(sorted((new, x, y))) in holes for x, y in itertools.combinations(kept, 2))
                    if gained > lost:
                        helpful += 1
        assert total == swaps and helpful == 1
        print("(%d,%d,3): every block needed. Weakest block of the public design leaves %d of %s triples uncovered;" % (v, k, seed_gap, format(len(count) + len(holes), ",")))
        print("          exactly %d of %s one-point swaps then helps. Weakest block of the record leaves %d." % (helpful, format(total, ","), final_gap))


def coordinates_from_planes(planes, n=15):
    """Give each of the 15 blocks a nonzero 4-bit label so that planes become hyperplanes."""
    third = {}
    for a, b in itertools.combinations(range(n), 2):
        common = frozenset(range(n))
        for plane in planes:
            if a in plane and b in plane:
                common &= plane
        assert len(common) == 3
        third[frozenset((a, b))] = next(iter(common - {a, b}))
    labels = {}
    basis = []

    for point in range(n):
        if point in labels:
            continue
        if len(basis) == 4:
            break
        bit = 1 << len(basis)
        known = list(labels.items())
        labels[point] = bit
        basis.append(point)
        for other, value in known:
            labels[third[frozenset((point, other))]] = value ^ bit
    assert sorted(labels.values()) == list(range(1, 16))
    for a, b in itertools.combinations(range(n), 2):
        assert labels[third[frozenset((a, b))]] == labels[a] ^ labels[b]
    return labels


def analyse_trap(path=None):
    path = path or ROOT / "data" / "trap_48_23_3_b15.json"
    blocks = [frozenset(b) for b in json.loads(Path(path).read_text())["blocks"]]
    assert len(blocks) == 15 and all(len(b) == 23 for b in blocks)
    covered = set()
    for b in blocks:
        covered.update(itertools.combinations(sorted(b), 3))
    holes = set(itertools.combinations(range(1, 49), 3)) - covered
    assert len(holes) == 1
    hole = next(iter(holes))
    index = {p: frozenset(i for i, b in enumerate(blocks) if p in b) for p in range(1, 49)}
    groups = collections.defaultdict(list)
    for p, where in index.items():
        groups[where].append(p)
    clones = {where: pts for where, pts in groups.items() if len(pts) == 3}
    assert len(clones) == 15 and all(len(where) == 7 for where in clones)
    assert all(len(index[p]) == 10 for p in hole)
    labels = coordinates_from_planes(list(clones))
    # Every 7-block set is the zero set of one nonzero linear form on the labels.
    forms = {}
    for where in clones:
        match = [f for f in range(1, 16)
                 if {i for i in range(15) if bin(labels[i] & f).count("1") % 2 == 0} == set(where)]
        assert len(match) == 1
        forms[where] = match[0]
    assert len(set(forms.values())) == 15
    # Every block is exactly full: 7 groups of 3, plus 2 of the 3 hole points.
    for i, b in enumerate(blocks):
        assert sum(i in where for where in clones) == 7 and len(b & set(hole)) == 2
    misses = [frozenset(range(15)) - index[p] for p in hole]
    assert sorted(len(m) for m in misses) == [5, 5, 5] and len(frozenset().union(*misses)) == 15
    for m in misses:
        for a, b, c in itertools.combinations(sorted(m), 3):
            assert labels[a] ^ labels[b] ^ labels[c] != 0
    # The numbers the run measured on this state.
    count = collections.Counter(s for b in blocks for s in itertools.combinations(sorted(b), 3))
    swaps, covering, lowest, lowest_covering = 0, 0, None, None
    for b in blocks:
        members = sorted(b)
        for out in members:
            kept = [p for p in members if p != out]
            lost = sum(count[tuple(sorted((out, x, y)))] == 1 for x, y in itertools.combinations(kept, 2))
            for new in range(1, 49):
                if new in b:
                    continue
                swaps += 1
                closes = new in hole and set(hole) <= set(kept) | {new}
                after = 1 + lost - (1 if closes else 0)
                lowest = after if lowest is None else min(lowest, after)
                if closes:
                    covering += 1
                    lowest_covering = after if lowest_covering is None else min(lowest_covering, after)
    assert (swaps, covering, lowest, lowest_covering) == (8625, 315, 31, 108)
    return {"blocks": blocks, "hole": hole, "clones": clones, "labels": labels, "forms": forms}


def check_trap():
    found = analyse_trap()
    print("(48,23,3) at 15 blocks: 45 points fall into 15 groups of 3 identical points, each group in 7 blocks; these")
    print("          7-block sets are exactly the planes of PG(3,2). The other 3 points %s are the one uncovered triple." % (found["hole"],))
    print("          Every block holds 21 + 2 = 23 points, exactly full. Of 8,625 one-point swaps, 315 cover the triple,")
    print("          and each of those uncovers at least 108 others. The best swap of any kind leaves 31 uncovered.")


def check_twins():
    seed, final = load("seeds", "42_12_3.json"), load("certificates", "42_12_3.json")
    def holds(blocks, p):
        return frozenset(i for i, b in enumerate(blocks) if p in b)
    def twins(blocks):
        groups = collections.defaultdict(list)
        for p in range(1, 43):
            groups[holds(blocks, p)].append(p)
        return sorted(tuple(g) for g in groups.values() if len(g) > 1)
    assert twins(seed) == [(40, 42)]
    assert twins(final) == [(15, 31), (40, 42)]
    assert len(holds(final, 15)) == 21 and len(holds(final, 40)) == 21
    assert len(holds(seed, 15) & holds(seed, 31)) == 7
    a, b = load("other_designs", "42_12_3_first_solve_74_blocks.json"), load("other_designs", "42_12_3_seed513_74_blocks.json")
    assert not set(final) & set(a) and not set(final) & set(b) and not set(a) & set(b)
    assert not set(final) & set(seed)
    print("(42,12,3): the public design has one pair of twin points, {40,42}. The record has a second, {15,31}, in the same")
    print("           21 blocks; in the public design those two share only 7. Three 74-block solutions share no block.")


def check_proposition_1():
    # GF(16) as polynomials mod x^4 + x + 1. Nonzero elements are the 15 points of PG(3,2).
    def times(a, b):
        out = 0
        while b:
            if b & 1:
                out ^= a
            a <<= 1
            if a & 16:
                a ^= 0b10011
            b >>= 1
        return out
    powers = [1]
    for _ in range(14):
        powers.append(times(powers[-1], 2))
    assert sorted(powers) == list(range(1, 16))
    # Three ovoids: the cosets of the subgroup of order 5.
    ovoids = [{powers[(3 * j + c) % 15] for j in range(5)} for c in range(3)]
    assert set().union(*ovoids) == set(range(1, 16))
    def on_plane(p, form):
        return bin(p & form).count("1") % 2 == 0
    planes = [{p for p in range(1, 16) if on_plane(p, f)} for f in range(1, 16)]
    # Each ovoid has no three collinear points and meets every plane.
    for o in ovoids:
        assert all(a ^ b ^ c != 0 for a, b, c in itertools.combinations(sorted(o), 3))
        assert all(o & plane for plane in planes)
    guest_sets = [plane for plane in planes for _ in range(3)] + [set(range(1, 16)) - o for o in ovoids]
    assert len(guest_sets) == 48
    blocks = {p: {g for g, s in enumerate(guest_sets) if p in s} for p in range(1, 16)}
    assert all(len(b) == 23 for b in blocks.values())
    uncovered = [t for t in itertools.combinations(range(48), 3) if not (guest_sets[t[0]] & guest_sets[t[1]] & guest_sets[t[2]])]
    assert uncovered == [(45, 46, 47)]
    print("Proposition 1: built from the planes of PG(3,2) and three ovoids, 48 guests in 15 photos of 23 miss exactly one trio.")


def check_proposition_2():
    planes = [[p for p in range(1, 16) if bin(p & f).count("1") % 2 == 0] for f in range(1, 16)]
    seats = [0] * 16
    found = 0
    tried = 0
    def place(point, left):
        nonlocal found, tried
        if point == 15:
            seats[15] = left
            tried += 1
            if all(sum(seats[p] for p in plane) % 4 == 1 for plane in planes):
                found += 1
            return
        for n in range(left + 1):
            seats[point] = n
            place(point + 1, left - n)
    place(1, 9)
    assert tried == 817190 and found == 0
    print("Proposition 2: of all 817,190 ways to place 9 spare seats on the 15 blocks, none meets every plane in 1 mod 4 seats.")


def main():
    structure = json.loads((ROOT / "data" / "structure.json").read_text())
    check_41(structure["41_9_3"])
    check_44(structure["44_11_3"])
    check_tightness()
    check_twins()
    check_trap()
    check_proposition_1()
    check_proposition_2()
    print("All structural claims check out.")


if __name__ == "__main__":
    main()
