#!/usr/bin/env python3
"""
Plot the loadDepWaitCycles distribution from gem5 stats.txt files.

Single file mode:
    python3 util/plot_load_dep_wait.py m5out/stats.txt

Compare baseline vs LVP (adds missing samples as 0-cycle dependents):
    python3 util/plot_load_dep_wait.py --baseline m5out_no_lvp/stats.txt \
                                       --lvp m5out_lvp/stats.txt

    python3 util/plot_load_dep_wait.py --baseline m5out_no_lvp/stats.txt \
                                       --lvp m5out_lvp/stats.txt \
                                       -o comparison.png
"""

import argparse
import re
import sys

import matplotlib.pyplot as plt
import numpy as np


def parse_stats(filepath):
    """Parse loadDepWaitCycles distribution from a gem5 stats file."""
    buckets = []  # (label, count)
    mean = None
    stdev = None
    samples = None
    overflows = 0

    with open(filepath) as f:
        for line in f:
            if "loadDepWaitCycles" not in line:
                continue

            if "::mean" in line:
                mean = float(line.split()[1])
            elif "::stdev" in line:
                stdev = float(line.split()[1])
            elif "::samples" in line:
                samples = int(line.split()[1])
            elif "::overflows" in line:
                overflows = int(line.split()[1])
            elif "::" in line:
                m = re.search(r"::(\d+-\d+)\s+(\d+)", line)
                if m:
                    label = m.group(1)
                    count = int(m.group(2))
                    buckets.append((label, count))

    if not buckets:
        print(f"Error: no loadDepWaitCycles data found in {filepath}",
              file=sys.stderr)
        sys.exit(1)

    return buckets, mean, stdev, samples, overflows


def adjusted_mean_stdev(buckets, overflows, extra_zeros):
    """Recompute mean and stdev after adding extra_zeros to the 0-bucket."""
    # Use bucket midpoints for approximation
    midpoints = []
    counts = []
    for label, count in buckets:
        lo, hi = label.split("-")
        mid = (int(lo) + int(hi)) / 2.0
        midpoints.append(mid)
        counts.append(count)

    midpoints = np.array(midpoints)
    counts = np.array(counts, dtype=np.float64)
    # Add the extra zeros to the first bucket (0-9, midpoint ~4.5)
    counts[0] += extra_zeros

    total = counts.sum() + overflows
    # Treat overflows as bucket midpoint 300 (conservative)
    overflow_mid = 300.0

    weighted_sum = (midpoints * counts).sum() + overflow_mid * overflows
    mean = weighted_sum / total

    weighted_sq_sum = (midpoints**2 * counts).sum() + overflow_mid**2 * overflows
    variance = weighted_sq_sum / total - mean**2
    stdev = np.sqrt(max(variance, 0))

    return mean, stdev, int(total)


def plot_single(buckets, mean, stdev, samples, overflows, output):
    labels = [b[0] for b in buckets]
    counts = np.array([b[1] for b in buckets], dtype=np.float64)
    total = counts.sum() + overflows
    pcts = counts / total * 100

    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.bar(x, pcts, color="#4C72B0", edgecolor="white", linewidth=0.3)

    ax.set_xlabel("Wait Cycles (bucket range)", fontsize=12)
    ax.set_ylabel("Percentage of Dependents (%)", fontsize=12)
    ax.set_title("Cycles Dependent Instructions Wait for Load Values",
                 fontsize=14)

    step = max(1, len(labels) // 15)
    ax.set_xticks(x[::step])
    ax.set_xticklabels(labels[::step], rotation=45, ha="right", fontsize=9)

    stats_text = (f"Mean: {mean:.2f} cycles\n"
                  f"Stdev: {stdev:.2f} cycles\n"
                  f"Samples: {samples:,}\n"
                  f"Overflows (>299): {overflows:,}")
    ax.text(0.97, 0.95, stats_text, transform=ax.transAxes,
            fontsize=10, verticalalignment="top", horizontalalignment="right",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="wheat",
                      alpha=0.8))

    bucket_width = 10
    mean_x = mean / bucket_width
    ax.axvline(x=mean_x, color="red", linestyle="--", linewidth=1.5,
               label=f"Mean = {mean:.1f}")
    ax.legend(loc="lower right", fontsize=10)

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    print(f"Saved histogram to {output}")


def plot_comparison(base_data, lvp_data, output):
    base_buckets, base_mean, base_stdev, base_samples, base_overflows = base_data
    lvp_buckets, lvp_mean, lvp_stdev, lvp_samples, lvp_overflows = lvp_data

    # Use baseline labels as the canonical set
    labels = [b[0] for b in base_buckets]
    base_counts = np.array([b[1] for b in base_buckets], dtype=np.float64)
    base_total = base_counts.sum() + base_overflows

    # Build LVP counts aligned to the same labels
    lvp_map = {b[0]: b[1] for b in lvp_buckets}
    lvp_counts = np.array([lvp_map.get(l, 0) for l in labels], dtype=np.float64)
    lvp_raw_total = lvp_counts.sum() + lvp_overflows

    # Add missing samples as 0-cycle dependents
    extra_zeros = max(0, int(base_total - lvp_raw_total))
    lvp_counts_adj = lvp_counts.copy()
    lvp_counts_adj[0] += extra_zeros
    lvp_adj_total = lvp_counts_adj.sum() + lvp_overflows

    # Recompute adjusted LVP mean/stdev
    lvp_adj_mean, lvp_adj_stdev, lvp_adj_samples = adjusted_mean_stdev(
        list(zip(labels, lvp_counts.astype(int))), lvp_overflows, extra_zeros)

    # Convert to percentages (normalized to same total for fair comparison)
    base_pcts = base_counts / base_total * 100
    lvp_pcts = lvp_counts_adj / lvp_adj_total * 100

    x = np.arange(len(labels))
    width = 0.38

    fig, ax = plt.subplots(figsize=(16, 7))
    ax.bar(x - width / 2, base_pcts, width, color="#4C72B0",
           edgecolor="white", linewidth=0.3, label="Baseline (no LVP)")
    ax.bar(x + width / 2, lvp_pcts, width, color="#DD8452",
           edgecolor="white", linewidth=0.3, label="LVP (adjusted)")

    ax.set_xlabel("Wait Cycles (bucket range)", fontsize=12)
    ax.set_ylabel("Percentage of Dependents (%)", fontsize=12)
    ax.set_title("Load Dependent Wait Cycles: Baseline vs LVP", fontsize=14)

    step = max(1, len(labels) // 15)
    ax.set_xticks(x[::step])
    ax.set_xticklabels(labels[::step], rotation=45, ha="right", fontsize=9)

    # Mean lines
    bucket_width = 10
    ax.axvline(x=base_mean / bucket_width, color="#4C72B0", linestyle="--",
               linewidth=1.5, label=f"Baseline mean = {base_mean:.1f}")
    ax.axvline(x=lvp_adj_mean / bucket_width, color="#DD8452", linestyle="--",
               linewidth=1.5, label=f"LVP adj. mean = {lvp_adj_mean:.1f}")

    # Stats boxes
    base_text = (f"Baseline\n"
                 f"Mean: {base_mean:.2f} cyc\n"
                 f"Stdev: {base_stdev:.2f} cyc\n"
                 f"Samples: {base_samples:,}")
    ax.text(0.97, 0.95, base_text, transform=ax.transAxes,
            fontsize=9, verticalalignment="top", horizontalalignment="right",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#B8CBE0",
                      alpha=0.85))

    lvp_text = (f"LVP (adjusted)\n"
                f"Mean: {lvp_adj_mean:.2f} cyc\n"
                f"Stdev: {lvp_adj_stdev:.2f} cyc\n"
                f"Samples: {lvp_adj_samples:,}\n"
                f"  (0-cyc added: {extra_zeros:,})")
    ax.text(0.97, 0.68, lvp_text, transform=ax.transAxes,
            fontsize=9, verticalalignment="top", horizontalalignment="right",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#F0CBA8",
                      alpha=0.85))

    # Reduction summary
    reduction = ((base_mean - lvp_adj_mean) / base_mean) * 100
    summary = f"Mean wait reduction: {reduction:.1f}%"
    ax.text(0.5, 0.95, summary, transform=ax.transAxes,
            fontsize=12, fontweight="bold",
            verticalalignment="top", horizontalalignment="center",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow",
                      alpha=0.9))

    ax.legend(loc="lower right", fontsize=9)

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    print(f"Saved comparison to {output}")
    print(f"\nBaseline: mean={base_mean:.2f} cyc, samples={base_samples:,}")
    print(f"LVP adj: mean={lvp_adj_mean:.2f} cyc, samples={lvp_adj_samples:,}"
          f" (added {extra_zeros:,} zero-cycle dependents)")
    print(f"Mean wait reduction: {reduction:.1f}%")


def main():
    parser = argparse.ArgumentParser(
        description="Plot loadDepWaitCycles distribution from gem5 stats. "
                    "Supports single file or baseline vs LVP comparison.")

    parser.add_argument("stats_file", nargs="?", default=None,
                        help="Path to a single gem5 stats.txt (single mode)")
    parser.add_argument("--baseline", type=str, default=None,
                        help="Baseline stats.txt (no LVP)")
    parser.add_argument("--lvp", type=str, default=None,
                        help="LVP stats.txt")
    parser.add_argument("-o", "--output", default=None,
                        help="Output PNG filename")
    args = parser.parse_args()

    compare_mode = args.baseline and args.lvp

    if not compare_mode and not args.stats_file:
        parser.error("Provide a stats_file for single mode, or "
                     "--baseline and --lvp for comparison mode.")

    if compare_mode:
        output = args.output or "loadDepWaitCycles_comparison.png"
        base_data = parse_stats(args.baseline)
        lvp_data = parse_stats(args.lvp)
        plot_comparison(base_data, lvp_data, output)
    else:
        output = args.output or "loadDepWaitCycles.png"
        buckets, mean, stdev, samples, overflows = parse_stats(args.stats_file)
        plot_single(buckets, mean, stdev, samples, overflows, output)


if __name__ == "__main__":
    main()
