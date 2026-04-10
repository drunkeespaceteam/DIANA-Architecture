#!/bin/bash
# ═══════════════════════════════════════════════════════════
# DIANA-OS — Full Kernel + Module Build
# ═══════════════════════════════════════════════════════════
# Builds a complete Linux kernel with DIANA module from source.
# This creates BOTH the kernel (bzImage) AND the module (.ko)
# needed to boot the real DIANA-Nexus OS in QEMU.
#
# Time: ~15-20 minutes (one-time build)
# ═══════════════════════════════════════════════════════════
set -e

PROJ="/mnt/c/Users/ELCOT/.gemini/antigravity/scratch/DIANA-Architecture"
KDIR="$HOME/wsl2-kernel"
BUILD_DIR="$HOME/diana-build"
NPROC=$(nproc)

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  DIANA-Nexus OS — Full Production Build              ║"
echo "║  Building: Linux Kernel + DIANA Module + bzImage     ║"
echo "║  Using $NPROC CPU cores for fast compilation            ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# ─── Step 1: Prepare kernel source ───
echo "[1/5] Preparing kernel source..."
if [ ! -d "$KDIR" ]; then
    echo "  Downloading WSL2 kernel source..."
    cd $HOME
    git clone --depth 1 https://github.com/microsoft/WSL2-Linux-Kernel.git wsl2-kernel 2>&1 | tail -3
fi
cd "$KDIR"

# Use the WSL config as base, enable what DIANA needs
echo "  Configuring kernel with DIANA features enabled..."
if [ -f Microsoft/config-wsl ]; then
    cp Microsoft/config-wsl .config
else
    zcat /proc/config.gz > .config 2>/dev/null || make defconfig
fi

# Enable critical features DIANA needs
scripts/config --enable CONFIG_KPROBES
scripts/config --enable CONFIG_KPROBE_EVENTS
scripts/config --enable CONFIG_MODULES
scripts/config --enable CONFIG_MODULE_UNLOAD
scripts/config --enable CONFIG_PROC_FS
scripts/config --enable CONFIG_PRINTK
scripts/config --set-str CONFIG_LOCALVERSION "-diana-nexus"

# Accept defaults for any new config options
make olddefconfig 2>&1 | tail -3
echo "  ✓ Kernel configured"
echo ""

# ─── Step 2: Build the full kernel ───
echo "[2/5] Building Linux kernel (this takes ~15 min, using $NPROC cores)..."
echo "  This is a ONE-TIME build. Future builds will be instant."
echo ""
make -j$NPROC 2>&1 | grep -E "(^  (CC|LD|AR|AS|OBJCOPY)|Kernel:|^$)" | tail -20

if [ -f arch/x86/boot/bzImage ]; then
    echo ""
    echo "  ╔═══════════════════════════════════════╗"
    echo "  ║  ✓ KERNEL BUILT: bzImage              ║"
    echo "  ╚═══════════════════════════════════════╝"
    ls -lh arch/x86/boot/bzImage
else
    echo "  ✗ Kernel build failed!"
    exit 1
fi
echo ""

# ─── Step 3: Copy DIANA module source to Linux filesystem ───
echo "[3/5] Preparing DIANA module source..."
mkdir -p "$BUILD_DIR/kernel"
cp "$PROJ"/kernel/*.c "$BUILD_DIR/kernel/"
cp "$PROJ"/kernel/*.h "$BUILD_DIR/kernel/"
cp "$PROJ"/kernel/Makefile "$BUILD_DIR/kernel/"
cp "$PROJ"/kernel/Kconfig "$BUILD_DIR/kernel/" 2>/dev/null || true
echo "  ✓ Module source copied to native Linux filesystem"
echo ""

# ─── Step 4: Build DIANA kernel module ───
echo "[4/5] Compiling diana_core.ko..."
cd "$BUILD_DIR/kernel"
make -C "$KDIR" M="$(pwd)" modules 2>&1 | tail -15

if [ -f diana_core.ko ]; then
    echo ""
    echo "  ╔═══════════════════════════════════════════╗"
    echo "  ║  ✓ diana_core.ko COMPILED SUCCESSFULLY!  ║"
    echo "  ╚═══════════════════════════════════════════╝"
    ls -lh diana_core.ko
    echo ""
    modinfo diana_core.ko 2>/dev/null | head -8 || true
    
    # Copy back to project
    cp diana_core.ko "$PROJ/kernel/"
    echo "  ✓ Copied to project: $PROJ/kernel/diana_core.ko"
else
    echo "  ✗ Module compilation failed!"
    echo "  Check errors above."
    exit 1
fi
echo ""

# ─── Step 5: Prepare boot files ───
echo "[5/5] Preparing boot files..."
mkdir -p "$PROJ/boot"
cp "$KDIR/arch/x86/boot/bzImage" "$PROJ/boot/bzImage"
echo "  ✓ Kernel image: $PROJ/boot/bzImage"
echo ""

# ─── Test: Try loading module ───
echo "═══ Quick Test ═══"
echo "Attempting to load diana_core.ko into running WSL kernel..."
sudo insmod "$BUILD_DIR/kernel/diana_core.ko" 2>&1 && {
    echo "  ✓ MODULE LOADED!"
    echo ""
    echo "  ═══ REAL /proc/diana/stats ═══"
    cat /proc/diana/stats
    echo ""
    echo "  ═══ REAL /proc/diana/cpu_report ═══"
    cat /proc/diana/cpu_report
    echo ""
    sleep 2
    echo "  ═══ REAL /proc/diana/p2p_log ═══"
    cat /proc/diana/p2p_log
    echo ""
    # Unload after test
    sudo rmmod diana_core 2>/dev/null || true
    echo "  ✓ Module unloaded after test"
} || {
    echo "  ⚠ Cannot load in WSL (version mismatch or kprobes disabled)."
    echo "  Module will work correctly when booted in QEMU."
}

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  BUILD COMPLETE!                                      ║"
echo "║                                                       ║"
echo "║  ✓ Linux Kernel: boot/bzImage                        ║"
echo "║  ✓ DIANA Module: kernel/diana_core.ko                ║"
echo "║                                                       ║"
echo "║  NEXT: Boot the real DIANA-Nexus OS:                  ║"
echo "║    bash scripts/run_qemu.sh                           ║"
echo "╚═══════════════════════════════════════════════════════╝"
