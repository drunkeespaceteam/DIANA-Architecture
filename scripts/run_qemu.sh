#!/bin/bash
# ═══════════════════════════════════════════════════
# DIANA-Nexus OS — Run in QEMU with GUI (SAFE!)
# ═══════════════════════════════════════════════════
# Your main OS is COMPLETELY SAFE!
# DIANA-Nexus boots inside this virtual machine with a
# full graphical desktop powered by SYNAPSE AI.
#
# Author: Sahidh — DIANA Architecture

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "╔══════════════════════════════════════════════╗"
echo "║  Starting DIANA-Nexus OS in QEMU             ║"
echo "║  Your main OS is COMPLETELY untouched!        ║"
echo "║  Close the QEMU window to exit               ║"
echo "╚══════════════════════════════════════════════╝"
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
    echo "╔══════════════════════════════════════════════════╗"
    echo "║  Building DIANA-Nexus Full OS Image              ║"
    echo "║  Includes: X11, Openbox, Chromium, PyTorch,      ║"
    echo "║  SYNAPSE AI daemon, and the GUI Desktop.         ║"
    echo "║  This will take several minutes...               ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo ""
    rm -rf /tmp/diana-initramfs
    mkdir -p /tmp/diana-initramfs
    cd /tmp/diana-initramfs

    # Download Ubuntu Base 22.04
    UBUNTU_URL="http://cdimage.ubuntu.com/ubuntu-base/releases/22.04/release/ubuntu-base-22.04.4-base-amd64.tar.gz"
    if ! command -v wget >/dev/null; then apt-get update && apt-get install -y wget; fi
    echo "[1/5] Downloading Ubuntu Base 22.04..."
    wget -qO ubuntu.tar.gz "$UBUNTU_URL"
    tar xzf ubuntu.tar.gz
    rm ubuntu.tar.gz

    cp /etc/resolv.conf etc/resolv.conf

    echo "[2/5] Installing system packages (X11, Openbox, Chromium, Python)..."
    
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
        
        # Install core packages + X11 + browser for kiosk GUI
        chroot . apt-get update
        DEBIAN_FRONTEND=noninteractive chroot . apt-get install -y --no-install-recommends \
            python3 python3-pip kmod python3-setuptools coreutils bash \
            xserver-xorg-core xserver-xorg-video-fbdev xinit openbox \
            chromium-browser fonts-inter dbus-x11 \
            xdotool xterm net-tools procps
            
        # Install PyTorch (CPU) for SYNAPSE LSTM daemon
        chroot . pip3 install torch --no-cache-dir --index-url https://download.pytorch.org/whl/cpu || \
        chroot . pip3 install torch --no-cache-dir --break-system-packages --index-url https://download.pytorch.org/whl/cpu
    "
    # Unmounting is automatic when unshare exits

    # Setup DIANA environment
    echo "[3/5] Installing DIANA-Nexus components..."
    mkdir -p proc/diana
    mkdir -p var/lib/diana/models
    mkdir -p usr/local/diana
    
    # Copy DIANA-Nexus source
    cp -r "$PROJECT_DIR/userspace" usr/local/diana/
    cp -r "$PROJECT_DIR/synapse" usr/local/diana/

    # Copy DIANA module if built
    if [ -f "$PROJECT_DIR/kernel/diana_core.ko" ]; then
        mkdir -p lib/modules
        cp "$PROJECT_DIR/kernel/diana_core.ko" lib/modules/
    fi

    echo "[4/5] Configuring boot sequence..."

    # Create Init Script (PID 1) — boots straight into GUI
    cat > init << 'INITEOF'
#!/bin/sh
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mount -t tmpfs tmpfs /tmp

hostname diana-nexus

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║  DIANA-Nexus OS v1.0 — Booting...                ║"
echo "║  SYNAPSE Autonomous Intelligence Active           ║"
echo "║  Kernel: DIANA-Nexus Kernel                       ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""

# Load DIANA kernel module
if [ -f /lib/modules/diana_core.ko ]; then
    insmod /lib/modules/diana_core.ko
    echo "[KERNEL] DIANA-Nexus kernel module loaded!"
fi

# Start DIANA GUI Web Server on port 8080
echo "[SYSTEM] Starting DIANA-Nexus GUI Server..."
cd /usr/local/diana
python3 userspace/diana_gui_server.py --port 8080 &
GUI_PID=$!
echo "[SYSTEM] GUI Server PID: $GUI_PID"

# Wait a moment for server to start
sleep 2

# Start DIANA PyTorch Intelligence Daemon
echo "[SYSTEM] Starting SYNAPSE AI Training Daemon..."
cd /usr/local/diana && python3 userspace/diana_trainer.py --daemon &
echo "[SYSTEM] SYNAPSE AI daemon started."

# Start X11 + Openbox + Chromium Kiosk Mode
echo "[SYSTEM] Launching graphical desktop..."

# Openbox autostart config — launches Chromium in kiosk mode
mkdir -p /root/.config/openbox
cat > /root/.config/openbox/autostart << 'AUTOSTART'
# Wait for GUI server
sleep 3

# Hide mouse cursor after 1 second of inactivity
xdotool mousemove 9999 9999 &

# Launch Chromium in kiosk mode pointing at the local GUI server
chromium-browser \
    --no-sandbox \
    --disable-gpu \
    --kiosk \
    --disable-translate \
    --disable-features=TranslateUI \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --no-default-browser-check \
    --window-size=1024,768 \
    http://localhost:8080 &
AUTOSTART
chmod +x /root/.config/openbox/autostart

# Start X
export DISPLAY=:0
if command -v startx >/dev/null 2>&1; then
    startx /usr/bin/openbox-session -- -config /usr/share/X11/xorg.conf.d/ &
    echo "[SYSTEM] X11 desktop started on :0"
else
    echo "[SYSTEM] X11 not available — fallback to console"
    echo "[SYSTEM] Access GUI at http://localhost:8080"
fi

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║  DIANA-Nexus Desktop READY                        ║"
echo "║  GUI: http://localhost:8080                        ║"
echo "║  Type 'poweroff' in console to shut down          ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""

# Drop to shell as fallback
exec /bin/sh
INITEOF
    chmod +x init
    sed -i 's/\r$//' init

    # Pack the giant initramfs
    echo "[5/5] Packing DIANA-Nexus OS image (this takes a moment)..."
    find . -print0 | cpio --null -H newc -o 2>/dev/null | gzip -9 > "$PROJECT_DIR/boot/initramfs.cpio.gz"
    cd "$PROJECT_DIR"
    rm -rf /tmp/diana-initramfs

    echo ""
    echo "✓ DIANA-Nexus OS image created at boot/initramfs.cpio.gz"
fi

INITRD="boot/initramfs.cpio.gz"

# Create disk image if not exists
if [ ! -f diana-disk.img ]; then
    echo "Creating disk image (64MB)..."
    dd if=/dev/zero of=diana-disk.img bs=1M count=64 2>/dev/null
fi

echo ""
echo "Launching QEMU..."
echo "  → Kernel: $KERNEL"
echo "  → Initrd: $INITRD"
echo "  → GUI available at http://localhost:8080 inside the VM"
echo ""

# Try with KVM first (faster), fall back to software emulation
# In graphical mode, QEMU shows a window with the VGA display
qemu-system-x86_64 \
    -kernel "$KERNEL" \
    -initrd "$INITRD" \
    -append "console=tty0 diana.synapse=1 diana.p2p=1 rdinit=/init vga=791" \
    -m 4096M \
    -smp 2 \
    -vga std \
    -drive file=diana-disk.img,format=raw,if=virtio \
    -device virtio-net-pci,netdev=net0 \
    -netdev user,id=net0,hostfwd=tcp::8080-:8080 \
    -enable-kvm 2>/dev/null || \
qemu-system-x86_64 \
    -kernel "$KERNEL" \
    -initrd "$INITRD" \
    -append "console=tty0 diana.synapse=1 diana.p2p=1 rdinit=/init vga=791" \
    -m 4096M \
    -smp 2 \
    -vga std \
    -device virtio-net-pci,netdev=net0 \
    -netdev user,id=net0,hostfwd=tcp::8080-:8080

echo ""
echo "QEMU exited. Your main OS is untouched."
