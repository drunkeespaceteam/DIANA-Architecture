#!/bin/bash
# ═══════════════════════════════════════════════════
# DIANA-OS — Flash to USB Drive (SAFE!)
# ═══════════════════════════════════════════════════
# Only touches the USB you specify!
# Your internal drive is NEVER touched!
#
# Author: Sahidh — DIANA Architecture

set -e

echo "╔══════════════════════════════════════════╗"
echo "║  DIANA-OS — Flash to USB                 ║"
echo "║  WARNING: This will ERASE the USB drive! ║"
echo "║  Your laptop drive is NOT touched!        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Check for ISO/image
if [ ! -f diana-os.iso ] && [ ! -f diana-os.img ]; then
    echo "No DIANA-OS image found!"
    echo "Create one first:"
    echo "  make iso    — Create ISO image"
    echo ""
    exit 1
fi

IMAGE="diana-os.iso"
[ -f diana-os.img ] && IMAGE="diana-os.img"

echo "Image: $IMAGE"
echo ""

# Show available drives
echo "Available drives:"
echo "─────────────────────────────────────────"
lsblk -d -o NAME,SIZE,MODEL,TRAN | grep -v "loop"
echo "─────────────────────────────────────────"
echo ""

read -p "Enter USB device name (e.g., sdb — NOT sda): " USB

# Safety checks
if [ -z "$USB" ]; then
    echo "No device specified. Aborting."
    exit 1
fi

if [ "$USB" = "sda" ]; then
    echo "╔══════════════════════════════════════════╗"
    echo "║  ERROR: sda is usually your main drive!  ║"
    echo "║  Use sdb or sdc for USB drives!          ║"
    echo "║  ABORTING for safety!                    ║"
    echo "╚══════════════════════════════════════════╝"
    exit 1
fi

if [ "$USB" = "nvme0n1" ]; then
    echo "ERROR: nvme0n1 is your NVMe drive! Use USB device."
    exit 1
fi

# Verify it's removable (USB check)
REMOVABLE=$(cat /sys/block/$USB/removable 2>/dev/null)
if [ "$REMOVABLE" != "1" ]; then
    echo "WARNING: /dev/$USB does not appear to be a removable drive!"
    read -p "Are you ABSOLUTELY sure this is a USB drive? (yes/no): " FORCE
    if [ "$FORCE" != "yes" ]; then
        echo "Aborting. Better safe than sorry!"
        exit 1
    fi
fi

echo ""
echo "This will COMPLETELY ERASE /dev/$USB !"
echo "Data on this drive CANNOT be recovered!"
echo ""
read -p "Type 'yes' to confirm flash to /dev/$USB: " CONFIRM

if [ "$CONFIRM" = "yes" ]; then
    echo ""
    echo "Unmounting /dev/$USB partitions..."
    umount /dev/${USB}* 2>/dev/null || true

    echo "Flashing DIANA-OS to /dev/$USB..."
    sudo dd if="$IMAGE" of="/dev/$USB" bs=4M status=progress conv=fsync

    sync
    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║  Done! DIANA-OS flashed to USB!          ║"
    echo "║                                          ║"
    echo "║  To boot:                                ║"
    echo "║    1. Restart your computer               ║"
    echo "║    2. Press F12/F2/ESC for boot menu     ║"
    echo "║    3. Select USB drive                   ║"
    echo "║                                          ║"
    echo "║  Your main OS boots normally without USB! ║"
    echo "╚══════════════════════════════════════════╝"
else
    echo "Aborting. Nothing was changed."
fi
