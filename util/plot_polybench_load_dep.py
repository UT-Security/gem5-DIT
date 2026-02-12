#!/usr/bin/env python3
"""
Plot mean loadDepWaitCycles across PolyBench benchmarks for the base
gem5 configuration.

Usage:
    python3 util/plot_polybench_load_dep.py                        # defaults
    python3 util/plot_polybench_load_dep.py --region 2             # second region
    python3 util/plot_polybench_load_dep.py -o results/load_dep.png
"""

import argparse
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

STAT_KEY = "board.processor.cores.core.loadDepWaitCycles::mean"


def parse_load_dep_mean(filepath, region=1):
    """Extract loadDepWaitCycles::mean from the given simulation region."""
    current_region = 0
    in_target = False

    with open(filepath) as f:
        for line in f:
            if "Begin Simulation Statistics" in line:
                current_region += 1
                in_target = (current_region == region)
                continue
            if "End Simulation Statistics" in line:
                if in_target:
                    break
                continue
            if in_target and line.startswith(STAT_KEY):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        return float(parts[1])
                    except ValueError:
                        return None
    return None


def collect_data(data_dir, region):
    """Collect loadDepWaitCycles::mean for all benchmarks under base."""
    base_dir = os.path.join(data_dir, "base")
    benchmarks = sorted(os.listdir(base_dir))
    values = {}

    for bench in benchmarks:
        stats_path = os.path.join(base_dir, bench, "m5out", "stats.txt")
        if not os.path.isfile(stats_path):
            print(f"Warning: missing {stats_path}", file=sys.stderr)
            continue
        val = parse_load_dep_mean(stats_path, region)
        if val is None:
            print(f"Warning: could not parse loadDepWaitCycles::mean from "
                  f"{stats_path} (region {region})", file=sys.stderr)
            continue
        values[bench] = val

    return benchmarks, values


def plot(benchmarks, values, output, show):
    """Create and save a bar chart."""
    # Filter to benchmarks with valid data, preserving sort order
    valid = [(b, values[b]) for b in benchmarks if b in values]
    names = [b.replace("_base", "") for b, _ in valid]
    vals = [v for _, v in valid]

    x = np.arange(len(names))

    fig, ax = plt.subplots(figsize=(20, 7))
    ax.bar(x, vals, color="#4C72B0", edgecolor="white", linewidth=0.3)

    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=45, ha="right", fontsize=9)
    ax.set_ylabel("Cycles", fontsize=12)
    ax.set_title("Average # of Cycles Dependent Instructions Wait for Load Value",
                 fontsize=14)

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    print(f"Saved plot to {output}")

    if show:
        plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Plot mean loadDepWaitCycles for PolyBench benchmarks "
                    "(base config).")
    parser.add_argument(
        "-d", "--data-dir",
        default="/home/rgangar/gem5/polybench",
        help="Root polybench results directory (default: %(default)s)")
    parser.add_argument(
        "-o", "--output",
        default="polybench_load_dep.png",
        help="Output image filename (default: %(default)s)")
    parser.add_argument(
        "--region", type=int, default=1,
        help="1-indexed simulation region to use (default: 1)")
    parser.add_argument(
        "--show", action="store_true",
        help="Display the plot interactively")
    args = parser.parse_args()

    benchmarks, values = collect_data(args.data_dir, args.region)
    plot(benchmarks, values, args.output, args.show)


if __name__ == "__main__":
    main()
