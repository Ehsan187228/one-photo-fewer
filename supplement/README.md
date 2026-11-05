# Supplement to "One Photo Fewer"

Everything needed to check the mathematical claims of the paper, with no Oris, no model and no network connection. Python 3.9 or later is enough for the checks. A C compiler is needed only to regenerate one record.

## Verification

```sh
python3 verify.py --self-test     # tests the checker on good and broken designs
python3 verify.py                 # the three headline records, under a second
python3 verify.py --all           # all 29 records, about a minute and a half
python3 verify.py --others        # adds nine further valid designs not counted among the 29, about a minute
python3 check_structure.py        # the grids, the twins and the trap, a few seconds
sh solver/regenerate_42_12_3.sh   # reruns GLM-5.3's search for the 74-block record, about half a minute
```

`verify.py` checks every required subset in two unrelated ways, and refuses a design with a repeated point, a point out of range, a duplicate block or a wrong count.

## Contents

| Path | What it holds |
|---|---|
| `verify.py` | Checks the designs against `records.csv` and the files against `MANIFEST.json` |
| `check_structure.py` | Rechecks the grids, the twins and the trap |
| `certificates/` | The 29 record designs, one file per entry (`v`, `k`, `t`, `claimed_size`, `blocks`) |
| `records.csv` | Each record: run, entry, new size, bar, frozen table value, where it started |
| `seeds/` | The three public designs the headline searches started from |
| `other_designs/` | Further valid designs not counted among the 29: two more 74-block (42,12,3) designs and six more from Run 2 |
| `solver/` | The two search programs behind the headline records, written by GLM-5.3 during Run 6, unchanged, the public starting design that regenerates the 74-block record, and the script that does it |
| `data/structure.json` | Grid coordinates for the (41,9,3) and (44,11,3) designs |
| `data/41_9_3_second_solution.json` | The second 167-block design |
| `data/trap_48_23_3_b15.json` | The stuck 15-block (48,23,3) state preserved in the run's record |
| `data/near_misses.csv` | Run 6: the 101 entries in the team's tables and six short tests |
| `data/six_runs.csv` | The six runs side by side |
| `data/usage_by_minute.csv` | Run 6 calls, generated and new input tokens per minute by model, and context read again (whole minutes) |
| `data/machine_by_minute.csv` | Run 6 load and busy cores |
| `data/search_traces.csv` | The search logs behind Figure 2 |
| `MANIFEST.json` | SHA-256 of every other file here; `verify.py` checks them |

## Credit

Starting designs come from the La Jolla Coverings Repository snapshot (D. Gordon, Zenodo, doi:10.5281/zenodo.19735294, CC BY 4.0) and its contributors, including Giovanni Acerbi and Alessandro Jurcovich; from WitnessFlow (car-b); and from public work by Zarco, Özdemir and the V3R1T4S contributors. Those sources keep their own terms. The changes made are the searches described in the paper.
