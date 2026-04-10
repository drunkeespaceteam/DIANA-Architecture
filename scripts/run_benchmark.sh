#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# DIANA-OS — One-Click Benchmark Comparison
# ═══════════════════════════════════════════════════════════════════════
# Runs the complete benchmark comparison:
#   1. Unloads DIANA module (if loaded) → runs BASELINE
#   2. Loads DIANA module + starts LSTM trainer → runs DIANA
#   3. Generates comparison report with REAL data
#
# Usage:
#   sudo bash scripts/run_benchmark.sh          # Full benchmark (~10 min)
#   sudo bash scripts/run_benchmark.sh --quick   # Quick benchmark (~3 min)
#
# SAFETY: This NEVER modifies your host Windows OS!
#         Everything runs inside WSL2's sandboxed Linux kernel.
#
# Author: Sahidh — DIANA Architecture
# ═══════════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

QUICK=""
if [ "$1" = "--quick" ]; then
    QUICK="--quick"
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                                                             ║"
echo "║   DIANA-OS — Real Performance Benchmark                     ║"
echo "║                                                             ║"
echo "║   Standard Linux Kernel  vs  DIANA Architecture             ║"
echo "║   (Von Neumann paradigm)    (Autonomous Components)        ║"
echo "║                                                             ║"
echo "║   All data is REAL — measured from:                         ║"
echo "║   • /proc/self/stat     (page faults, CPU ticks)            ║"
echo "║   • /proc/vmstat        (cache, swap, paging)               ║"
echo "║   • perf_counter_ns()   (nanosecond wall clock)             ║"
echo "║   • /proc/diana/stats   (SYNAPSE intelligence metrics)     ║"
echo "║                                                             ║"
echo "║   ⚠  Your host Windows OS is COMPLETELY UNTOUCHED!         ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# ── Pre-flight checks ──
echo "◆ Pre-flight checks..."

# Check we're running as root (needed for insmod/rmmod)
if [ "$(id -u)" -ne 0 ]; then
    echo "  ✗ This script needs root (for insmod/rmmod)"
    echo "  Run: sudo bash scripts/run_benchmark.sh"
    exit 1
fi
echo "  ✓ Running as root"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "  ✗ Python3 not found!"
    echo "  Install: sudo apt install python3"
    exit 1
fi
echo "  ✓ Python3 found"

# Check kernel module
if [ -f kernel/diana_core.ko ]; then
    echo "  ✓ diana_core.ko found"
else
    echo "  ⚠ diana_core.ko not found — building..."
    
    # Try to build
    KDIR="/lib/modules/$(uname -r)/build"
    if [ ! -d "$KDIR" ]; then
        # Check custom kernel
        if [ -d "$HOME/wsl2-kernel" ]; then
            KDIR="$HOME/wsl2-kernel"
        else
            echo "  ✗ No kernel build directory found!"
            echo "  Run: bash scripts/setup_wsl_kernel.sh first"
            exit 1
        fi
    fi
    
    cd kernel/
    cp diana_core.c diana_core_main.c 2>/dev/null || true
    make -C "$KDIR" M="$(pwd)" modules 2>&1 | tail -5
    cd "$PROJECT_DIR"
    
    if [ -f kernel/diana_core.ko ]; then
        echo "  ✓ diana_core.ko built successfully"
    else
        echo "  ✗ Build failed! Cannot run DIANA benchmark."
        echo "  The BASELINE benchmark will still run."
        echo "  Press Enter to continue with baseline only, or Ctrl+C to abort."
        read
    fi
fi

# Check test data
BENCH_DATA="/tmp/diana_benchmark/data"
if [ -d "$BENCH_DATA" ] && [ -f "$BENCH_DATA/sequential_10mb.bin" ]; then
    echo "  ✓ Benchmark data files exist"
else
    echo "  Creating benchmark data files..."
    mkdir -p "$BENCH_DATA/small_files"
    dd if=/dev/urandom of="$BENCH_DATA/sequential_10mb.bin" bs=1M count=10 2>/dev/null
    dd if=/dev/urandom of="$BENCH_DATA/large_100mb.bin" bs=1M count=100 2>/dev/null
    for i in $(seq 1 1000); do
        dd if=/dev/urandom of="$BENCH_DATA/small_files/file_$i.dat" bs=4K count=1 2>/dev/null
    done
    echo "  ✓ Benchmark data created"
fi
echo ""

# ── Drop caches for fair measurement ──
echo "◆ Preparing system for fair measurement..."
echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true
sync
echo "  ✓ Page cache dropped, buffers synced"
echo ""

# ── PHASE 1: BASELINE ──
echo "╔══════════════════════════════════════════════════════╗"
echo "║  PHASE 1: BASELINE — Standard Linux Kernel          ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Make sure DIANA is NOT loaded
if grep -q diana_core /proc/modules 2>/dev/null; then
    echo "  Unloading DIANA module for baseline..."
    rmmod diana_core 2>/dev/null || true
    sleep 1
fi

echo "  Running baseline benchmarks..."
python3 benchmarks/benchmark_suite.py --baseline-only $QUICK
echo ""

# Drop caches again for DIANA run
echo "◆ Resetting system state for DIANA run..."
echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true
sync
sleep 2
echo "  ✓ System reset"
echo ""

# ── PHASE 2: DIANA ──
if [ -f kernel/diana_core.ko ]; then
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║  PHASE 2: DIANA — SYNAPSE Intelligence Active       ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo ""
    
    python3 benchmarks/benchmark_suite.py --diana-only $QUICK
    echo ""
    
    # Unload module after benchmark
    echo "  Cleaning up: unloading DIANA module..."
    rmmod diana_core 2>/dev/null || true
else
    echo "═══ Skipping DIANA benchmark (module not available) ═══"
fi

# ── PHASE 3: COMPARISON REPORT ──
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  PHASE 3: COMPARISON REPORT                         ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

python3 benchmarks/compare_results.py --latest 2>/dev/null || {
    echo "  Could not generate comparison (need both baseline and DIANA results)"
    echo "  Results are saved individually in: /tmp/diana_benchmark/results/"
}

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Benchmark Complete!                                       ║"
echo "║                                                            ║"
echo "║  Results: /tmp/diana_benchmark/results/                    ║"
echo "║                                                            ║"
echo "║  Re-run comparison:                                        ║"
echo "║    python3 benchmarks/compare_results.py --latest          ║"
echo "║                                                            ║"
echo "║  View past results:                                        ║"
echo "║    python3 benchmarks/compare_results.py --list            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
