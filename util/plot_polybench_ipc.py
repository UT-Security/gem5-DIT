#!/usr/bin/env python3
"""
Plot IPC across PolyBench benchmarks for different gem5 configurations,
normalized to the base configuration.

Usage:
    python3 util/plot_polybench_ipc.py                        # defaults
    python3 util/plot_polybench_ipc.py --region 2             # second region
    python3 util/plot_polybench_ipc.py -o results/ipc.png     # custom output
    python3 util/plot_polybench_ipc.py --show                 # interactive
"""

import argparse
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

CONFIGS = ["base", "lvp", "comp_simp", "lvp_comp_simp"]
BAR_CONFIGS = ["lvp", "comp_simp", "lvp_comp_simp"]
BAR_LABELS = ["LVP", "Comp Simp", "LVP + Comp Simp"]
BAR_COLORS = ["#4C72B0", "#DD8452", "#55A868"]

IPC_KEY = "board.processor.cores.core.ipc"


def parse_ipc(filepath, region=1):
    """Extract IPC from the given simulation region of a gem5 stats file.

    Parameters
    ----------
    filepath : str
        Path to a gem5 stats.txt file.
    region : int
        1-indexed simulation region to read from.

    Returns
    -------
    float or None
        The IPC value, or None if not found.
    """
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
                    break  # past our region, stop
                continue
            if in_target and line.startswith(IPC_KEY):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        return float(parts[1])
                    except ValueError:
                        return None
    return None


def collect_data(data_dir, region):
    """Collect IPC values for all configs and benchmarks.

    Returns
    -------
    tuple
        (benchmarks, data) where benchmarks is a sorted list of benchmark
        directory names and data is {config: {benchmark: ipc}}.
    """
    benchmarks = sorted(os.listdir(os.path.join(data_dir, "base")))
    data = {}

    for config in CONFIGS:
        data[config] = {}
        for bench in benchmarks:
            stats_path = os.path.join(data_dir, config, bench, "m5out", "stats.txt")
            if not os.path.isfile(stats_path):
                print(f"Warning: missing {stats_path}", file=sys.stderr)
                continue
            ipc = parse_ipc(stats_path, region)
            if ipc is None:
                print(f"Warning: could not parse IPC from {stats_path} "
                      f"(region {region})", file=sys.stderr)
                continue
            data[config][bench] = ipc

    return benchmarks, data


def normalize(benchmarks, data):
    """Normalize IPC values to the base configuration.

    Returns
    -------
    dict
        {config: [normalized_ipc_for_each_benchmark]}
        Benchmarks missing a base IPC are assigned NaN.
    """
    normalized = {c: [] for c in BAR_CONFIGS}
    for bench in benchmarks:
        base_ipc = data["base"].get(bench)
        for config in BAR_CONFIGS:
            cfg_ipc = data[config].get(bench)
            if base_ipc and cfg_ipc:
                normalized[config].append(cfg_ipc / base_ipc)
            else:
                normalized[config].append(float("nan"))
    return normalized


def plot(benchmarks, normalized, output, show):
    """Create and save the grouped bar chart."""
    x = np.arange(len(benchmarks))
    n_bars = len(BAR_CONFIGS)
    width = 0.25

    fig, ax = plt.subplots(figsize=(20, 7))

    for i, (config, label, color) in enumerate(
            zip(BAR_CONFIGS, BAR_LABELS, BAR_COLORS)):
        values = normalized[config]
        offset = (i - (n_bars - 1) / 2) * width
        ax.bar(x + offset, values, width, label=label, color=color,
               edgecolor="white", linewidth=0.3)

    # Baseline reference line
    ax.axhline(y=1.0, color="red", linestyle="--", linewidth=1.2,
               label="Baseline")

    # Strip _base suffix for display
    display_names = [b.replace("_base", "") for b in benchmarks]
    ax.set_xticks(x)
    ax.set_xticklabels(display_names, rotation=45, ha="right", fontsize=9)

    ax.set_ylabel("Normalized IPC (vs. base)", fontsize=12)
    ax.set_title("PolyBench IPC Normalized to Base Configuration", fontsize=14)
    ax.legend(fontsize=10)

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    print(f"Saved plot to {output}")

    if show:
        plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Plot PolyBench IPC across gem5 configurations, "
                    "normalized to the base config.")
    parser.add_argument(
        "-d", "--data-dir",
        default="/home/rgangar/gem5/polybench",
        help="Root polybench results directory (default: %(default)s)")
    parser.add_argument(
        "-o", "--output",
        default="polybench_ipc.png",
        help="Output image filename (default: %(default)s)")
    parser.add_argument(
        "--region", type=int, default=1,
        help="1-indexed simulation region to use (default: 1)")
    parser.add_argument(
        "--show", action="store_true",
        help="Display the plot interactively")
    args = parser.parse_args()

    benchmarks, data = collect_data(args.data_dir, args.region)
    normalized = normalize(benchmarks, data)
    plot(benchmarks, normalized, args.output, args.show)


if __name__ == "__main__":
    main()
