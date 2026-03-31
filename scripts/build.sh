#!/bin/bash
# ═══════════════════════════════════════════════════
# DIANA-OS — Full Build Script
# ═══════════════════════════════════════════════════
# Build everything: kernel module + userspace
# Author: Sahidh — DIANA Architecture

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "╔══════════════════════════════════════╗"
echo "║  Building DIANA-OS v0.1              ║"
echo "║  SYNAPSE Chip Intelligence           ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── Step 1: Check dependencies ──
echo "[1/7] Checking dependencies..."
MISSING=0

command -v gcc >/dev/null 2>&1 || { echo "  ✗ gcc — Install: sudo apt install gcc"; MISSING=1; }
command -v make >/dev/null 2>&1 || { echo "  ✗ make — Install: sudo apt install make"; MISSING=1; }
command -v python3 >/dev/null 2>&1 || { echo "  ✗ python3 — Install: sudo apt install python3"; MISSING=1; }

command -v qemu-system-x86_64 >/dev/null 2>&1 && \
    echo "  ✓ qemu available" || \
    echo "  ○ qemu not installed (optional — for VM testing)"

if [ $MISSING -eq 1 ]; then
    echo ""
    echo "Install missing dependencies and try again."
    exit 1
fi

echo "  ✓ All required dependencies found"
echo ""

# ── Step 2: Build kernel module ──
echo "[2/7] Building DIANA kernel module..."
if [ -d /lib/modules/$(uname -r)/build ]; then
    # Handle naming collision: diana_core.c -> diana_core_main.c
    cp kernel/diana_core.c kernel/diana_core_main.c 2>/dev/null || true
    cd kernel/
    make -C /lib/modules/$(uname -r)/build M=$(pwd) modules 2>&1 || {
        echo "  ⚠ Kernel module build failed (need kernel headers)"
        echo "  Install: sudo apt install linux-headers-$(uname -r)"
        cd "$PROJECT_DIR"
    }
    cd "$PROJECT_DIR"
    if [ -f kernel/diana_core.ko ]; then
        echo "  ✓ diana_core.ko built successfully"
    else
        echo "  ⚠ Module not built (continuing with userspace only)"
    fi
else
    echo "  ⚠ Kernel build directory not found"
    echo "  Install: sudo apt install linux-headers-$(uname -r)"
fi
echo ""

# ── Step 3: Load module for testing ──
echo "[3/7] Loading DIANA kernel module..."
if [ -f kernel/diana_core.ko ]; then
    sudo insmod kernel/diana_core.ko 2>/dev/null && {
        echo "  ✓ Module loaded"
    } || {
        echo "  ⚠ Module already loaded or cannot load"
    }
else
    echo "  ⚠ diana_core.ko not found (skipping)"
fi
echo ""

# ── Step 4: Verify /proc entries ──
echo "[4/7] Verifying kernel interface..."
if [ -d /proc/diana ]; then
    echo "  ✓ /proc/diana/ exists"
    ls -la /proc/diana/ 2>/dev/null | while read line; do
        echo "    $line"
    done
    echo ""
    echo "  Stats preview:"
    head -20 /proc/diana/stats 2>/dev/null | while read line; do
        echo "    $line"
    done
else
    echo "  ⚠ /proc/diana/ not found (module not loaded)"
fi
echo ""

# ── Step 5: Install Python dependencies ──
echo "[5/7] Installing Python dependencies..."
python3 -c "import torch" 2>/dev/null && \
    echo "  ✓ PyTorch available" || {
    echo "  Installing PyTorch..."
    pip3 install torch --quiet 2>/dev/null || \
        echo "  ⚠ PyTorch install failed (LSTM features unavailable)"
}

python3 -c "import psutil" 2>/dev/null && \
    echo "  ✓ psutil available" || {
    echo "  Installing psutil..."
    pip3 install psutil --quiet 2>/dev/null || \
        echo "  ⚠ psutil install failed (monitor features unavailable)"
}
echo ""

# ── Step 6: Run tests ──
echo "[6/7] Running tests..."
echo ""

echo "  → SYNAPSE Intelligence Tests"
python3 tests/test_synapse.py 2>&1 | while read line; do
    echo "    $line"
done
echo ""

if [ -d /proc/diana ]; then
    echo "  → Kernel Module Tests"
    bash tests/test_kernel_module.sh 2>&1 | while read line; do
        echo "    $line"
    done
    echo ""

    echo "  → P2P Bus Tests"
    bash tests/test_p2p_bus.sh 2>&1 | while read line; do
        echo "    $line"
    done
else
    echo "  ⚠ Skipping kernel tests (module not loaded)"
fi
echo ""

# ── Step 7: Start daemon ──
echo "[7/7] Starting DIANA daemon..."
python3 userspace/diana_trainer.py --daemon 2>/dev/null && {
    echo "  ✓ DIANA trainer daemon started"
} || {
    echo "  ⚠ Daemon mode not available (run manually)"
    echo "  Run: python3 userspace/diana_trainer.py &"
}

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  DIANA-OS Build Complete!                ║"
echo "║                                          ║"
echo "║  Dashboard: python3 userspace/diana_ui.py║"
echo "║  Status:    bash userspace/diana_ctl.sh  ║"
echo "║  QEMU:      bash scripts/run_qemu.sh    ║"
echo "╚══════════════════════════════════════════╝"
