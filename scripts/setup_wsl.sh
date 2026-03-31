#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# DIANA-OS — WSL2 Environment Setup
# ═══════════════════════════════════════════════════════════════════════
# Master setup script for running DIANA-OS inside WSL2.
# Installs all dependencies, compiles kernel modules, and prepares
# the benchmark environment.
#
# Usage:
#   bash scripts/setup_wsl.sh          # Full setup
#   bash scripts/setup_wsl.sh --quick  # Skip kernel, deps only
#
# Author: Sahidh — DIANA Architecture
# ═══════════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

QUICK_MODE=0
if [ "$1" = "--quick" ]; then
    QUICK_MODE=1
fi

echo "╔══════════════════════════════════════════╗"
echo "║  DIANA-OS — WSL2 Environment Setup      ║"
echo "║  Installing everything you need          ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Step 1: System dependencies ──
echo "[1/6] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    build-essential gcc g++ make \
    flex bison libssl-dev libelf-dev bc \
    python3 python3-pip python3-venv \
    linux-tools-common \
    sysstat procps coreutils \
    git wget curl jq \
    stress-ng fio sysbench \
    2>&1 | tail -5
echo "  ✓ System packages installed"
echo ""

# ── Step 2: Python dependencies ──
echo "[2/6] Installing Python dependencies..."
pip3 install --quiet --break-system-packages \
    torch --index-url https://download.pytorch.org/whl/cpu \
    2>&1 | tail -3 || {
    echo "  ⚠ PyTorch CPU install from index failed, trying pip default..."
    pip3 install --quiet --break-system-packages torch 2>&1 | tail -3 || {
        echo "  ⚠ PyTorch install failed. LSTM benchmarks will use fallback mode."
    }
}

pip3 install --quiet --break-system-packages \
    psutil numpy matplotlib \
    2>&1 | tail -3 || echo "  ⚠ Some Python deps failed"

echo "  ✓ Python dependencies installed"
echo ""

# ── Step 3: Verify kernel module support ──
echo "[3/6] Checking kernel module support..."
KVER=$(uname -r)
echo "  Running kernel: $KVER"

if [ -d "/lib/modules/$KVER/build" ]; then
    echo "  ✓ Kernel build directory found"
    KDIR="/lib/modules/$KVER/build"
elif [ -d "$HOME/wsl2-kernel" ]; then
    echo "  ✓ Custom WSL2 kernel source found"
    KDIR="$HOME/wsl2-kernel"
else
    echo "  ⚠ No kernel build directory!"
    echo ""
    echo "  You need to compile a custom WSL2 kernel first:"
    echo "    bash scripts/setup_wsl_kernel.sh"
    echo ""
    if [ $QUICK_MODE -eq 0 ]; then
        echo "  Running kernel setup now..."
        bash "$SCRIPT_DIR/setup_wsl_kernel.sh"
        KDIR="$HOME/wsl2-kernel"
    else
        echo "  Skipping (--quick mode). Module compilation will fail."
        KDIR=""
    fi
fi
echo ""

# ── Step 4: Compile DIANA kernel modules ──
echo "[4/6] Compiling DIANA kernel modules..."
if [ -n "$KDIR" ]; then
    cd "$PROJECT_DIR/kernel"

    # Handle diana_core naming collision
    cp diana_core.c diana_core_main.c 2>/dev/null || true

    echo "  Building against: $KDIR"
    make -C "$KDIR" M="$(pwd)" modules 2>&1 | tail -10 || {
        echo "  ⚠ Module compilation failed!"
        echo "  This usually means kernel headers don't match."
        echo "  Try: bash scripts/setup_wsl_kernel.sh"
    }

    cd "$PROJECT_DIR"

    if [ -f kernel/diana_core.ko ]; then
        echo "  ✓ diana_core.ko compiled successfully!"
        ls -lh kernel/diana_core.ko
    else
        echo "  ⚠ diana_core.ko not produced"
    fi
else
    echo "  ⚠ Skipped (no kernel build directory)"
fi
echo ""

# ── Step 5: Set up benchmark environment ──
echo "[5/6] Setting up benchmark environment..."

# Create benchmark data directory
mkdir -p /tmp/diana_benchmark/{data,results,models}

# Generate test files for I/O benchmarks (real files, not /dev/zero)
echo "  Generating benchmark data files..."

# 10MB sequential file (simulates document/source code)
if [ ! -f /tmp/diana_benchmark/data/sequential_10mb.bin ]; then
    dd if=/dev/urandom of=/tmp/diana_benchmark/data/sequential_10mb.bin \
       bs=1M count=10 2>/dev/null
    echo "  ✓ 10MB sequential test file"
fi

# 100MB large file (simulates build artifact / database)
if [ ! -f /tmp/diana_benchmark/data/large_100mb.bin ]; then
    dd if=/dev/urandom of=/tmp/diana_benchmark/data/large_100mb.bin \
       bs=1M count=100 2>/dev/null
    echo "  ✓ 100MB large test file"
fi

# 1000 small files (simulates source tree)
SMALL_DIR="/tmp/diana_benchmark/data/small_files"
if [ ! -d "$SMALL_DIR" ] || [ $(ls "$SMALL_DIR" 2>/dev/null | wc -l) -lt 1000 ]; then
    mkdir -p "$SMALL_DIR"
    for i in $(seq 1 1000); do
        dd if=/dev/urandom of="$SMALL_DIR/file_$i.dat" bs=4K count=1 2>/dev/null
    done
    echo "  ✓ 1000 small test files (4KB each)"
fi

echo "  ✓ Benchmark environment ready"
echo ""

# ── Step 6: Verify everything works ──
echo "[6/6] Running verification checks..."
echo ""

# Check Python
echo "  Python:"
python3 --version 2>&1 | sed 's/^/    /'
python3 -c "import torch; print(f'    PyTorch {torch.__version__}')" 2>/dev/null || \
    echo "    PyTorch: NOT AVAILABLE"
python3 -c "import psutil; print(f'    psutil {psutil.__version__}')" 2>/dev/null || \
    echo "    psutil: NOT AVAILABLE"
python3 -c "import numpy; print(f'    numpy {numpy.__version__}')" 2>/dev/null || \
    echo "    numpy: NOT AVAILABLE"
echo ""

# Check kernel module
echo "  Kernel Module:"
if [ -f kernel/diana_core.ko ]; then
    echo "    diana_core.ko: READY ($(stat -c%s kernel/diana_core.ko) bytes)"
    modinfo kernel/diana_core.ko 2>/dev/null | grep -E "^(description|author|version)" | sed 's/^/    /' || true
else
    echo "    diana_core.ko: NOT BUILT"
fi
echo ""

# Check benchmarking tools
echo "  Benchmark Tools:"
command -v stress-ng >/dev/null 2>&1 && echo "    stress-ng: ✓" || echo "    stress-ng: ✗"
command -v fio >/dev/null 2>&1 && echo "    fio: ✓" || echo "    fio: ✗"
command -v sysbench >/dev/null 2>&1 && echo "    sysbench: ✓" || echo "    sysbench: ✗"
echo ""

echo "╔════════════════════════════════════════════════════╗"
echo "║  DIANA-OS WSL2 Environment — READY!               ║"
echo "║                                                    ║"
echo "║  Next: Run the benchmark comparison:               ║"
echo "║    sudo bash scripts/run_benchmark.sh              ║"
echo "║                                                    ║"
echo "║  Or load the module manually:                      ║"
echo "║    sudo insmod kernel/diana_core.ko                ║"
echo "║    cat /proc/diana/stats                           ║"
echo "╚════════════════════════════════════════════════════╝"
