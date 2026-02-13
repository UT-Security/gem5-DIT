#!/bin/bash
#
# Cross-compile all PolyBench/C benchmarks for ARM aarch64 (static).
# Usage: ./util/compile_polybench.sh  (from gem5 root)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

POLYBENCH_DIR="$ROOT_DIR/PolyBenchC"
OUT_DIR="$ROOT_DIR/polybench_binaries"
CC=aarch64-linux-gnu-gcc
DATASET="${1:-MINI_DATASET}"
CFLAGS="-static -O2 -march=armv8.4-a+nosve -D$DATASET"
#-DPOLYBENCH_DUMP_ARRAYS
M5_INCLUDE="$ROOT_DIR/include"
M5_LIBDIR="$ROOT_DIR/util/m5/build/arm64/out"
LIBS="-lm"

mkdir -p "$OUT_DIR"

PASS=0
FAIL=0

while IFS= read -r line; do
    # Skip blank lines
    [ -z "$line" ] && continue

    # line is e.g. ./datamining/correlation/correlation.c
    src="$POLYBENCH_DIR/${line#./}"
    bench_dir="$(dirname "$src")"
    bench_name="$(basename "$src" .c)"
    out="$OUT_DIR/${bench_name}_base"

    echo "[CC] $bench_name"
    if $CC $CFLAGS \
        -I "$POLYBENCH_DIR/utilities" \
        -I "$bench_dir" \
        -I "$M5_INCLUDE" \
        "$POLYBENCH_DIR/utilities/polybench.c" \
        "$src" \
        -o "$out" \
        -L "$M5_LIBDIR" -lm5 $LIBS; then
        PASS=$((PASS + 1))
    else
        echo "[FAIL] $bench_name"
        FAIL=$((FAIL + 1))
    fi
done < "$POLYBENCH_DIR/utilities/benchmark_list"

echo ""
echo "=== Compilation complete: $PASS passed, $FAIL failed ==="
echo "Binaries in: $OUT_DIR"
