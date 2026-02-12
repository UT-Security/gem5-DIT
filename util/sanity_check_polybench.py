#!/usr/bin/env python3
"""
Sanity check: diff .err files (array dumps) between base and other configs.

Compares the DUMP_ARRAYS section of each benchmark's .CONDOR.ERR file
across configs to ensure gem5 modifications didn't break correctness.

Usage:
    python3 util/sanity_check_polybench.py
    python3 util/sanity_check_polybench.py -d /path/to/polybench
"""

import argparse
import os
import sys

CONFIGS = ["base", "lvp", "comp_simp", "lvp_comp_simp"]
OTHER_CONFIGS = ["lvp", "comp_simp", "lvp_comp_simp"]


def extract_dump(filepath):
    """Extract the DUMP_ARRAYS section from a .CONDOR.ERR file."""
    lines = []
    in_dump = False
    with open(filepath) as f:
        for line in f:
            if "==BEGIN DUMP_ARRAYS==" in line:
                in_dump = True
                lines.append(line)
                continue
            if "==END   DUMP_ARRAYS==" in line:
                lines.append(line)
                in_dump = False
                continue
            if in_dump:
                lines.append(line)
    return lines


def main():
    parser = argparse.ArgumentParser(
        description="Sanity check polybench .err files against base config.")
    parser.add_argument(
        "-d", "--data-dir",
        default="/home/rgangar/gem5/polybench",
        help="Root polybench results directory (default: %(default)s)")
    args = parser.parse_args()

    base_dir = os.path.join(args.data_dir, "base")
    benchmarks = sorted(os.listdir(base_dir))

    all_passed = True

    for bench in benchmarks:
        base_err = os.path.join(base_dir, bench,
                                f"{bench}.CONDOR.ERR")
        if not os.path.isfile(base_err):
            print(f"SKIP {bench}: no base .err file")
            continue

        base_dump = extract_dump(base_err)
        if not base_dump:
            print(f"SKIP {bench}: no DUMP_ARRAYS in base .err")
            continue

        bench_passed = True
        for config in OTHER_CONFIGS:
            cfg_err = os.path.join(args.data_dir, config, bench,
                                   f"{bench}.CONDOR.ERR")
            if not os.path.isfile(cfg_err):
                print(f"FAIL {bench} [{config}]: .err file missing")
                bench_passed = False
                all_passed = False
                continue

            cfg_dump = extract_dump(cfg_err)

            if base_dump != cfg_dump:
                print(f"FAIL {bench} [{config}]: array dump differs")
                bench_passed = False
                all_passed = False

        if bench_passed:
            print(f"PASS {bench}")

    print()
    if all_passed:
        print("ALL 30 BENCHMARKS PASSED")
    else:
        print("SOME BENCHMARKS FAILED")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
