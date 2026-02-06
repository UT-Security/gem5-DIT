#!/bin/bash
#
# Run all polybench binaries with and without LVP, scheduled across all cores.
# Usage: ./util/run_polybench.sh  (from gem5 root)

set -e

# Resolve gem5 root as the parent of the directory containing this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

GEM5=$ROOT_DIR/build/ARM/gem5.fast
CONFIG=$ROOT_DIR/configs/example/arm/fdp_neoverse_v2_binary.py
BINARY_DIR=$ROOT_DIR/polybench_binaries
MAX_JOBS=$(nproc)

BENCHMARKS=($(ls "$BINARY_DIR"))

echo "Found ${#BENCHMARKS[@]} benchmarks, scheduling across $MAX_JOBS cores"
echo "============================================"

run_bench() {
    local bench=$1
    local suffix=$2
    local extra_args=$3
    local outdir="benchmark_out_${suffix}/${bench}"

    mkdir -p "$outdir"
    echo "[START] $bench ($suffix)"
    $GEM5 -d "$outdir" $CONFIG --binary "$BINARY_DIR/$bench" $extra_args \
        > "$outdir/stdout.log" 2>&1
    echo "[DONE]  $bench ($suffix)"
}

export -f run_bench
export GEM5 CONFIG BINARY_DIR

# Phase 1: baseline (no LVP)
echo ""
echo "=== Phase 1: Baseline (no LVP) ==="
echo ""
parallel_pids=()

for bench in "${BENCHMARKS[@]}"; do
    run_bench "$bench" "base" "" &
    parallel_pids+=($!)

    # If we've hit the max, wait for one to finish
    while (( ${#parallel_pids[@]} >= MAX_JOBS )); do
        new_pids=()
        for pid in "${parallel_pids[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                new_pids+=("$pid")
            fi
        done
        parallel_pids=("${new_pids[@]}")
        if (( ${#parallel_pids[@]} >= MAX_JOBS )); then
            sleep 1
        fi
    done
done

# Wait for all baseline runs to finish
for pid in "${parallel_pids[@]}"; do
    wait "$pid"
done

echo ""
echo "=== Phase 2: LVP Enabled ==="
echo ""
parallel_pids=()

for bench in "${BENCHMARKS[@]}"; do
    run_bench "$bench" "lvp" "--enable-lvp" &
    parallel_pids+=($!)

    while (( ${#parallel_pids[@]} >= MAX_JOBS )); do
        new_pids=()
        for pid in "${parallel_pids[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                new_pids+=("$pid")
            fi
        done
        parallel_pids=("${new_pids[@]}")
        if (( ${#parallel_pids[@]} >= MAX_JOBS )); then
            sleep 1
        fi
    done
done

for pid in "${parallel_pids[@]}"; do
    wait "$pid"
done

echo ""
echo "=== All runs complete ==="
echo "Baseline results in: benchmark_out_base/"
echo "LVP results in:      benchmark_out_lvp/"
