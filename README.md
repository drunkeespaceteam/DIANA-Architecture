# DIANA-OS

> A Linux-based operating system where each hardware component has its own SYNAPSE intelligence chip, components communicate peer-to-peer, and the CPU is a passive observer.

## The Problem
The Von Neumann architecture (1945) routes every operation through the CPU. In modern computing, this causes the "Memory Wall" — the CPU is 10,000x faster than memory but spends 40-50% of its time waiting for data.

## The Solution
**DIANA-OS** bakes distributed intelligence into the kernel itself. Each component is autonomous. The CPU stops being a permission gatekeeper.

### Validated Results (gem5)
*   **2.78x** faster than traditional architecture
*   **98%** lower cache miss latency
*   **CPU commands eliminated**: 100%
*   *Validated on DDR4-2400 with L1=32KB L2=256KB*

## Architecture

```text
[SYNAPSE-RAM] ⟷ [SYNAPSE-GPU]
      ↕                ↕
[SYNAPSE-SSD] ⟷ [SYNAPSE-CACHE]
      ↓ (status only)
[CPU OBSERVER]
commands_issued: 0
```

*   **Kernel Core**: Intercepts `kmalloc`, VFS `read`, and context switches (C module)
*   **P2P Bus**: Spinlock-protected message passing between components
*   **Userspace SYNAPSE**: Real PyTorch LSTM running continuously, feeding hints to the kernel
*   **CPU Observer**: Locked to 0 commands. If it ever issues a command, it throws a kernel `BUG()`

---

## Safe Ways To Run DIANA-OS

> **⚠️ NEVER flash to your main drive!** Always use VM or USB for testing!

### Safest — QEMU Virtual Machine
Your main OS is completely untouched! DIANA-OS runs inside a virtual machine.
```bash
make qemu
```

### Bootable USB
Flash to a USB stick, boot from it. Your main internal drive remains unaffected.
```bash
make iso
make usb
```

### VirtualBox
Create the ISO with `make iso`, then create a new VM in VirtualBox and boot from the ISO.

---

## How To Build (Linux Required)

```bash
git clone https://github.com/drunkeespaceteam/DIANA-Architecture.git
cd DIANA-OS

# 1. Build everything
make all

# 2. Run all tests (must pass!)
make test

# 3. Load into kernel (Safe — it's a module!)
make load

# 4. Check what DIANA sees
make status
```

### Running the Intelligence Layer

```bash
# Start userspace LSTM daemon
sudo bash userspace/diana_ctl.sh start

# Watch live dashboard
python3 userspace/diana_ui.py
```

---

## Author
**Sahidh**
Conceived and built starting from a mobile phone. Pure curiosity.
