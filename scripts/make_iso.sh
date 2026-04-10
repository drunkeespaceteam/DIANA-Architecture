#!/bin/bash
# ═══════════════════════════════════════════════════
# DIANA-OS — Create Bootable ISO
# ═══════════════════════════════════════════════════
# Author: Sahidh — DIANA Architecture

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "╔══════════════════════════════════════════╗"
echo "║  Creating DIANA-OS Bootable ISO           ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Check grub-mkrescue
command -v grub-mkrescue >/dev/null 2>&1 || {
    echo "grub-mkrescue not found!"
    echo "Install: sudo apt install grub-common grub-pc-bin xorriso"
    exit 1
}

# Setup ISO directory structure
echo "[1/4] Setting up ISO structure..."
rm -rf iso/
mkdir -p iso/boot/grub

# Copy kernel
if [ -f boot/bzImage ]; then
    cp boot/bzImage iso/boot/
    echo "  ✓ Kernel image copied"
else
    echo "  ⚠ No bzImage found — use host kernel or build one"
    HOST_KERNEL="/boot/vmlinuz-$(uname -r)"
    if [ -f "$HOST_KERNEL" ]; then
        cp "$HOST_KERNEL" iso/boot/bzImage
        echo "  ✓ Using host kernel"
    else
        echo "  ✗ No kernel available"
        exit 1
    fi
fi

# Copy initramfs
if [ -f boot/initramfs.cpio.gz ]; then
    cp boot/initramfs.cpio.gz iso/boot/
    echo "  ✓ Initramfs copied"
else
    echo "  ⚠ No initramfs — run scripts/run_qemu.sh first to create one"
fi

# Create GRUB config
echo "[2/4] Creating GRUB config..."
cat > iso/boot/grub/grub.cfg << 'EOF'
set timeout=5
set default=0

# DIANA-Nexus OS theme
set color_normal=cyan/black
set color_highlight=white/blue

menuentry "DIANA-Nexus OS — SYNAPSE Chip Intelligence" {
    linux /boot/bzImage console=ttyS0 console=tty0 diana.synapse=1 diana.p2p=1
    initrd /boot/initramfs.cpio.gz
}

menuentry "DIANA-Nexus OS — Debug Mode (verbose)" {
    linux /boot/bzImage console=ttyS0 console=tty0 diana.synapse=1 diana.debug=1 loglevel=7
    initrd /boot/initramfs.cpio.gz
}

menuentry "DIANA-Nexus OS — Safe Mode (no SYNAPSE)" {
    linux /boot/bzImage console=ttyS0 console=tty0 diana.synapse=0
    initrd /boot/initramfs.cpio.gz
}
EOF
echo "  ✓ GRUB config created"

# Build ISO
echo "[3/4] Building ISO image..."
grub-mkrescue -o diana-os.iso iso/ 2>/dev/null

echo "[4/4] Verifying..."
if [ -f diana-os.iso ]; then
    SIZE=$(du -h diana-os.iso | cut -f1)
    echo "  ✓ diana-os.iso created ($SIZE)"
else
    echo "  ✗ ISO creation failed"
    exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  DIANA-Nexus OS ISO Created!                       ║"
echo "║                                              ║"
echo "║  Test:  qemu-system-x86_64 -cdrom            ║"
echo "║           diana-os.iso -m 512M                ║"
echo "║                                              ║"
echo "║  Flash: sudo dd if=diana-os.iso               ║"
echo "║           of=/dev/sdX bs=4M                   ║"
echo "╚══════════════════════════════════════════════╝"

# Cleanup
rm -rf iso/
