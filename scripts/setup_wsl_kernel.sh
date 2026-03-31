#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# DIANA-OS — Custom WSL2 Kernel Compilation
# ═══════════════════════════════════════════════════════════════════════
# Compiles the Microsoft WSL2 kernel from source with:
#   - CONFIG_MODULES=y     (load .ko modules)
#   - CONFIG_KPROBES=y     (kprobe hooks for DIANA)
#   - CONFIG_PROC_FS=y     (/proc/diana/ interface)
#
# After this script, you must:
#   1. Copy the kernel to Windows: cp arch/x86/boot/bzImage /mnt/c/Users/<YOU>/
#   2. Create C:\Users\<YOU>\.wslconfig with:
#        [wsl2]
#        kernel=C:\\Users\\<YOU>\\bzImage
#   3. Restart WSL2: wsl --shutdown && wsl
#
# Author: Sahidh — DIANA Architecture
# ═══════════════════════════════════════════════════════════════════════

set -e

echo "╔═══════════════════════════════════════════════════════╗"
echo "║  DIANA-OS — Custom WSL2 Kernel Builder               ║"
echo "║  This gives us kprobe + module support               ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Detect Windows username for .wslconfig path
WIN_USER=$(cmd.exe /C "echo %USERNAME%" 2>/dev/null | tr -d '\r' || echo "")
if [ -z "$WIN_USER" ]; then
    WIN_USER=$(ls /mnt/c/Users/ | grep -v -E "^(Public|Default|All Users|Default User)$" | head -1)
fi
echo "Detected Windows user: $WIN_USER"
echo ""

# ── Step 1: Install build dependencies ──
echo "[1/6] Installing kernel build dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    build-essential flex bison libssl-dev libelf-dev \
    bc dwarves python3 git wget cpio \
    2>&1 | tail -3
echo "  ✓ Build dependencies installed"
echo ""

# ── Step 2: Get WSL2 kernel source ──
KERNEL_DIR="$HOME/wsl2-kernel"
WSL_KERNEL_TAG="linux-msft-wsl-6.1.21.2"  # Stable WSL2 kernel

echo "[2/6] Getting WSL2 kernel source..."
if [ -d "$KERNEL_DIR" ]; then
    echo "  Kernel source already exists at $KERNEL_DIR"
    echo "  Delete it to re-download: rm -rf $KERNEL_DIR"
else
    echo "  Cloning Microsoft WSL2 kernel (this takes a few minutes)..."
    git clone --depth 1 \
        --branch "$WSL_KERNEL_TAG" \
        https://github.com/microsoft/WSL2-Linux-Kernel.git \
        "$KERNEL_DIR" 2>&1 | tail -3
    echo "  ✓ Kernel source downloaded"
fi
echo ""

cd "$KERNEL_DIR"

# ── Step 3: Configure kernel ──
echo "[3/6] Configuring kernel with DIANA requirements..."

# Start from Microsoft's default WSL2 config
if [ -f Microsoft/config-wsl ]; then
    cp Microsoft/config-wsl .config
    echo "  Using Microsoft's WSL2 config as base"
else
    # Fallback: use current running config
    zcat /proc/config.gz > .config 2>/dev/null || make defconfig
    echo "  Using default config"
fi

# Enable required features for DIANA-OS
# These are the critical kernel options we need
cat >> .config << 'DIANA_CONFIG'

# ═══ DIANA-OS Required Kernel Options ═══
# Module support (load diana_core.ko)
CONFIG_MODULES=y
CONFIG_MODULE_UNLOAD=y
CONFIG_MODULE_FORCE_UNLOAD=y
CONFIG_MODVERSIONS=y

# Kprobes (intercept kmalloc, vfs_read, schedule)
CONFIG_KPROBES=y
CONFIG_KPROBE_EVENTS=y
CONFIG_HAVE_KPROBES=y

# /proc filesystem (DIANA interface)
CONFIG_PROC_FS=y
CONFIG_PROC_SYSCTL=y

# Performance counters (benchmarking)
CONFIG_PERF_EVENTS=y
CONFIG_HW_PERF_EVENTS=y

# Debug helpers
CONFIG_PRINTK=y
CONFIG_DYNAMIC_DEBUG=y
CONFIG_DEBUG_KERNEL=y

# BPF support (future eBPF DIANA extensions)
CONFIG_BPF=y
CONFIG_BPF_SYSCALL=y
DIANA_CONFIG

# Resolve any config dependencies
make olddefconfig 2>&1 | tail -5
echo "  ✓ Kernel configured with DIANA requirements"
echo ""

# ── Step 4: Compile kernel ──
NPROC=$(nproc)
echo "[4/6] Compiling kernel with $NPROC cores (this takes 5-15 minutes)..."
echo "  Building..."
make -j"$NPROC" bzImage 2>&1 | tail -5
echo ""

# Also build module support infrastructure
echo "  Building module support..."
make -j"$NPROC" modules_prepare 2>&1 | tail -3
echo "  ✓ Kernel compiled successfully!"
echo ""

# ── Step 5: Install headers locally ──
echo "[5/6] Installing kernel headers for module compilation..."
sudo make headers_install INSTALL_HDR_PATH=/usr/local 2>&1 | tail -3

# Create symlink so module Makefile can find the build directory
KERNEL_VERSION=$(make kernelrelease 2>/dev/null)
echo "  Kernel version: $KERNEL_VERSION"
sudo mkdir -p "/lib/modules/$KERNEL_VERSION"
sudo ln -sf "$KERNEL_DIR" "/lib/modules/$KERNEL_VERSION/build"
echo "  ✓ Headers installed, build symlink created"
echo ""

# ── Step 6: Copy kernel to Windows ──
echo "[6/6] Deploying custom kernel..."
BZIMAGE="arch/x86/boot/bzImage"
if [ -f "$BZIMAGE" ]; then
    # Copy to Windows user directory
    WIN_KERNEL="/mnt/c/Users/$WIN_USER/diana-wsl-kernel"
    cp "$BZIMAGE" "$WIN_KERNEL" 2>/dev/null || {
        echo "  ⚠ Could not copy to Windows. Copy manually:"
        echo "    cp $KERNEL_DIR/$BZIMAGE /mnt/c/Users/$WIN_USER/diana-wsl-kernel"
    }

    # Create .wslconfig
    WSLCONFIG="/mnt/c/Users/$WIN_USER/.wslconfig"
    WIN_KERNEL_PATH="C:\\\\Users\\\\$WIN_USER\\\\diana-wsl-kernel"

    if [ -f "$WSLCONFIG" ]; then
        echo "  ⚠ .wslconfig already exists. Back it up and add:"
        echo "    [wsl2]"
        echo "    kernel=$WIN_KERNEL_PATH"
    else
        cat > "$WSLCONFIG" << WSLEOF
[wsl2]
kernel=$WIN_KERNEL_PATH
memory=4GB
processors=4
WSLEOF
        echo "  ✓ Created .wslconfig with custom kernel path"
    fi

    echo ""
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║  Custom WSL2 Kernel READY!                           ║"
    echo "║                                                      ║"
    echo "║  Kernel: $WIN_KERNEL_PATH"
    echo "║  Version: $KERNEL_VERSION"
    echo "║                                                      ║"
    echo "║  NEXT STEPS:                                         ║"
    echo "║  1. Exit WSL:  exit                                  ║"
    echo "║  2. PowerShell: wsl --shutdown                       ║"
    echo "║  3. Reopen WSL (it now uses DIANA kernel!)           ║"
    echo "║  4. Verify:  uname -r  (should show $KERNEL_VERSION)║"
    echo "║  5. Compile DIANA: cd DIANA-OS && make module        ║"
    echo "╚═══════════════════════════════════════════════════════╝"
else
    echo "  ✗ bzImage not found! Kernel compilation may have failed."
    echo "  Check: $KERNEL_DIR/$BZIMAGE"
    exit 1
fi
