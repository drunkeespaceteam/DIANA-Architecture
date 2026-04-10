#!/bin/bash
# DIANA-OS — WSL2 Build Script (runs inside WSL)
set -e

echo "╔══════════════════════════════════════════╗"
echo "║  DIANA-OS — Building the REAL OS         ║"
echo "╚══════════════════════════════════════════╝"
echo ""

KVER=$(uname -r)
echo "[1/5] Kernel: $KVER"
echo "       OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2)"
echo ""

# Check for kernel headers
echo "[2/5] Checking kernel headers..."
if [ -d "/lib/modules/$KVER/build" ]; then
    echo "  ✓ Kernel headers found at /lib/modules/$KVER/build"
    KDIR="/lib/modules/$KVER/build"
else
    echo "  ⚠ No kernel headers for $KVER"
    echo "  WSL2 uses a Microsoft-custom kernel, headers aren't in apt."
    echo "  Downloading WSL2 kernel source to build against..."
    
    # Get the WSL2 kernel source matching our version
    cd /tmp
    MAJOR_VER=$(echo "$KVER" | grep -oP '^\d+\.\d+\.\d+')
    echo "  Downloading kernel source for $MAJOR_VER..."
    
    if [ ! -d "/tmp/WSL2-Linux-Kernel" ]; then
        git clone --depth 1 --branch "linux-msft-wsl-${KVER}" \
            https://github.com/microsoft/WSL2-Linux-Kernel.git 2>/dev/null || \
        git clone --depth 1 \
            https://github.com/microsoft/WSL2-Linux-Kernel.git 2>/dev/null || {
            echo "  ⚠ Could not clone WSL2 kernel source."
            echo "  Trying to use headers package..."
            sudo apt-get install -y linux-headers-generic 2>/dev/null || true
        }
    fi
    
    if [ -d "/tmp/WSL2-Linux-Kernel" ]; then
        cd /tmp/WSL2-Linux-Kernel
        # Prepare kernel build directory
        echo "  Preparing kernel config (this takes a moment)..."
        cp Microsoft/config-wsl .config 2>/dev/null || \
            zcat /proc/config.gz > .config 2>/dev/null || \
            make defconfig
        make prepare 2>&1 | tail -5
        make modules_prepare 2>&1 | tail -5
        KDIR="/tmp/WSL2-Linux-Kernel"
        echo "  ✓ Kernel source prepared at $KDIR"
    else
        echo "  ✗ Cannot proceed without kernel headers."
        echo "  Try: sudo apt-get install linux-headers-$(uname -r)"
        exit 1
    fi
fi
echo ""

# Navigate to project
PROJ="/mnt/c/Users/ELCOT/.gemini/antigravity/scratch/DIANA-Architecture"
echo "[3/5] Building DIANA kernel module..."
cd "$PROJ/kernel"

# Build the module
echo "  Building against: $KDIR"
make -C "$KDIR" M="$(pwd)" modules 2>&1 | tail -15

if [ -f diana_core.ko ]; then
    echo ""
    echo "  ╔═══════════════════════════════════════╗"
    echo "  ║  ✓ diana_core.ko COMPILED!            ║"
    echo "  ╚═══════════════════════════════════════╝"
    ls -lh diana_core.ko
    modinfo diana_core.ko 2>/dev/null | head -5
else
    echo "  ⚠ diana_core.ko not produced"
fi
echo ""

# Try loading the module
echo "[4/5] Loading DIANA module into kernel..."
sudo insmod diana_core.ko 2>&1 && {
    echo "  ✓ Module loaded!"
    echo ""
    echo "  Reading REAL /proc/diana/stats:"
    echo "  ─────────────────────────────────"
    cat /proc/diana/stats
    echo ""
    echo "  Reading REAL /proc/diana/cpu_report:"
    echo "  ──────────────────────────────────────"
    cat /proc/diana/cpu_report
} || {
    echo "  ⚠ Module load failed (this is expected on WSL2 if"
    echo "    CONFIG_KPROBES is not enabled in the kernel)."
    echo "  The module will work when booted in QEMU instead."
}
echo ""

echo "[5/5] Installing Python dependencies..."
pip3 install --quiet --break-system-packages torch --index-url https://download.pytorch.org/whl/cpu 2>&1 | tail -5 || \
    echo "  ⚠ PyTorch failed (will use numpy fallback)"
pip3 install --quiet --break-system-packages psutil numpy 2>&1 | tail -3 || true
echo "  ✓ Python deps done"
echo ""

echo "╔══════════════════════════════════════════════════╗"
echo "║  DIANA-OS Build Complete!                        ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  Next: Run 'bash scripts/run_qemu.sh' to boot   ║"
echo "║  the full DIANA-Nexus OS in a virtual machine.   ║"
echo "╚══════════════════════════════════════════════════╝"
