#!/bin/bash
# ═══════════════════════════════════════════════════
# DIANA-OS — Run in QEMU (SAFE!)
# ═══════════════════════════════════════════════════
# Your main OS is COMPLETELY SAFE!
# DIANA-OS runs inside this virtual machine!
#
# Author: Sahidh — DIANA Architecture

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "╔══════════════════════════════════════════╗"
echo "║  Starting DIANA-OS in QEMU               ║"
echo "║  Your main OS is COMPLETELY untouched!    ║"
echo "║  Press Ctrl+A then X to exit QEMU         ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Check for kernel image
if [ ! -f boot/bzImage ]; then
    echo "No kernel image found at boot/bzImage"
    
    # Get correct home directory even if running as sudo
    REAL_USER=${SUDO_USER:-$USER}
    USER_HOME=$(eval echo ~$REAL_USER)
    
    # Check if the user previously built the custom kernel in WSL
    WSL_KERNEL="$USER_HOME/wsl2-kernel/arch/x86/boot/bzImage"
    HOST_KERNEL="/boot/vmlinuz-$(uname -r)"

    if [ -f "$WSL_KERNEL" ]; then
        echo "Found your custom WSL2 kernel! Copying to boot/bzImage..."
        mkdir -p boot
        cp "$WSL_KERNEL" boot/bzImage
        KERNEL="boot/bzImage"
    elif [ -f "$HOST_KERNEL" ]; then
        KERNEL="$HOST_KERNEL"
        echo "Using host kernel: $KERNEL"
    else
        echo "No kernel available. Please ensure your custom kernel was built."
        exit 1
    fi
else
    KERNEL="boot/bzImage"
fi

# Ensure QEMU is installed
if ! command -v qemu-system-x86_64 >/dev/null; then
    echo "QEMU not installed. Installing now..."
    sudo apt-get update && sudo apt-get install -y qemu-system-x86 qemu-kvm
fi

# Create initramfs if not exists
if [ ! -f boot/initramfs.cpio.gz ]; then
    echo "Creating Ubuntu Linux OS Rootfs (with Native glibc PyTorch)..."
    echo "This will take space and time, please wait."
    rm -rf /tmp/diana-initramfs
    mkdir -p /tmp/diana-initramfs
    cd /tmp/diana-initramfs

    # Download Ubuntu Base 22.04 (Requires no musl-libc hacks)
    UBUNTU_URL="http://cdimage.ubuntu.com/ubuntu-base/releases/22.04/release/ubuntu-base-22.04.4-base-amd64.tar.gz"
    if ! command -v wget >/dev/null; then apt-get update && apt-get install -y wget; fi
    wget -qO ubuntu.tar.gz "$UBUNTU_URL"
    tar xzf ubuntu.tar.gz
    rm ubuntu.tar.gz

    cp /etc/resolv.conf etc/resolv.conf

    echo "Isolating Host OS from VM mounts using Linux unshare..."
    echo "Staging Neural AI Daemon (Native glibc PyTorch)..."
    
    # Run dangerous chroot operations safely inside an isolated mount namespace
    unshare -m bash -c "
        # Create virtual filesystems so apt and pip work seamlessly
        mount -t proc proc proc/
        mount -t sysfs sys sys/
        mount -t tmpfs tmp dev/
        mkdir -p dev/pts
        mount -t devpts devpts dev/pts/
        mknod -m 666 dev/null c 1 3
        mknod -m 666 dev/urandom c 1 9
        mknod -m 666 dev/random c 1 8
        mknod -m 622 dev/console c 5 1
        
        # Install Python, pip, and Kernel utilities via apt
        chroot . apt-get update
        DEBIAN_FRONTEND=noninteractive chroot . apt-get install -y --no-install-recommends \
            python3 python3-pip kmod python3-setuptools coreutils bash
            
        # Install genuine PyPI PyTorch without glibc compatibility layers
        chroot . pip3 install torch --no-cache-dir --index-url https://download.pytorch.org/whl/cpu || \
        chroot . pip3 install torch --no-cache-dir --break-system-packages --index-url https://download.pytorch.org/whl/cpu
    "
    # Unmounting is automatic when unshare exits, strictly protecting your host!

    # Setup DIANA environment
    mkdir -p proc/diana
    mkdir -p var/lib/diana/models
    mkdir -p usr/local/diana
    
    # Copy DIANA-OS python source
    cp -r "$PROJECT_DIR/userspace" usr/local/diana/
    cp -r "$PROJECT_DIR/synapse" usr/local/diana/

    # Copy DIANA module if built
    if [ -f "$PROJECT_DIR/kernel/diana_core.ko" ]; then
        mkdir -p lib/modules
        cp "$PROJECT_DIR/kernel/diana_core.ko" lib/modules/
    fi

    # Create Init Script (PID 1)
    cat > init << 'INITEOF'
#!/bin/sh
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev

echo "╔═══════════════════════════════════════════════╗"
echo "║  DIANA-OS v1.0 — Booting Full OS...          ║"
echo "║  SYNAPSE Autonomous Intelligence Active        ║"
echo "╚═══════════════════════════════════════════════╝"

# Load DIANA module
if [ -f /lib/modules/diana_core.ko ]; then
    insmod /lib/modules/diana_core.ko
    echo "[SYSTEM] DIANA kernel module loaded!"
    
    echo "[SYSTEM] Starting DIANA PyTorch Intelligence Daemon..."
    cd /usr/local/diana && python3 userspace/diana_trainer.py --daemon || echo "Warning: AI daemon failed to start"
fi

echo ""
echo "DIANA-OS Root Shell Ready. Type 'poweroff' to exit."
exec /bin/sh
INITEOF
    chmod +x init
    sed -i 's/\r$//' init

    # Pack the giant initramfs
    echo "Packing full standalone ISO payload (this takes a moment)..."
    find . -print0 | cpio --null -H newc -o 2>/dev/null | gzip -9 > "$PROJECT_DIR/boot/initramfs.cpio.gz"
    cd "$PROJECT_DIR"
    rm -rf /tmp/diana-initramfs

    echo "Full Initramfs created at boot/initramfs.cpio.gz"
fi

INITRD="boot/initramfs.cpio.gz"

# Create disk image if not exists
if [ ! -f diana-disk.img ]; then
    echo "Creating disk image (64MB)..."
    dd if=/dev/zero of=diana-disk.img bs=1M count=64 2>/dev/null
fi

echo ""
echo "Launching QEMU..."
echo ""

# Try with KVM first (faster), fall back to software emulation
qemu-system-x86_64 \
    -kernel "$KERNEL" \
    -initrd "$INITRD" \
    -append "console=ttyS0 diana.synapse=1 diana.p2p=1 rdinit=/init" \
    -nographic \
    -m 4096M \
    -smp 2 \
    -drive file=diana-disk.img,format=raw,if=virtio \
    -device virtio-net-pci,netdev=net0 \
    -netdev user,id=net0 \
    -enable-kvm 2>/dev/null || \
qemu-system-x86_64 \
    -kernel "$KERNEL" \
    -initrd "$INITRD" \
    -append "console=ttyS0 diana.synapse=1 rdinit=/init" \
    -nographic \
    -m 4096M

echo ""
echo "QEMU exited. Your main OS is untouched."
