# DIANA-Nexus OS Architecture
**Predictive Decentralized Data Orchestration Layer**

![DIANA OS Concept](userspace/gui/assets/logo.png) <!-- Conceptual placeholder -->

## The Problem: The Memory Wall
For over 80 years, computing has been bound by the Von Neumann architecture. In this traditional model, the Central Processing Unit (CPU) must explicitly orchestrate all data movement. If the GPU needs a texture from the SSD, the CPU must wake up, issue the interrupt, pull the data through the system bus into RAM, and then send it to the GPU. 

As hardware has advanced, this has created the **Von Neumann Bottleneck (The Memory Wall)**. The CPU wastes an enormous portion of its clock cycles simply acting as a traffic controller, generating heat and causing micro-stutters when fetching data.

## The DIANA Solution
DIANA (Decentralized Intelligence Architecture for Neural Autonomy) completely eliminates this bottleneck. Instead of a CPU-centric architecture, DIANA introduces a **Hybrid Predictive Distributed Architecture**, splitting the OS into two distinct domains:

1. **The Control Plane (CPU / Kernel):** The CPU acts as a passive observer. It is 100% responsible for process scheduling, capability-based security (Context Tagging), and acting as the final fallback referee, but it is **0% involved in data movement.**
2. **The Data Plane (SYNAPSE / P2P Hardware):** Hardware components (RAM, SSD, GPU) are equipped with autonomous intelligence units (SYNAPSE chips). These act as decentralized agents that communicate directly via a Peer-to-Peer (P2P) bus to move data autonomously based on predictive modeling.

### How it Works (Delegated Autonomy)
Using Reinforcement Learning (Q-Learning) combined with a frequency-based Long Short-Term Memory (LSTM) fallback, the P2P components accurately predict what file or memory block will be requested next. 

If you boot a video game, the SSD's SYNAPSE unit detects the sequential read pattern. Before the game's engine even attempts to execute the `read()` system call, the SSD has already transmitted the required assets directly to the RAM cache over the P2P bus. 

When the CPU inevitably requests the data for the application, it registers an instant Cache Hit. **The OS natively provides transparent acceleration without requiring any application-level rewrite.**

### Safety Guarantees & Fallbacks
- **No Deadlocks:** The custom P2P bus utilizes a strict 5µs asynchronous non-blocking timeout limit. If an agent does not receive its data in time, it aborts the distributed fetch. Deadlocks are mathematically avoided, while livelock and network congestion are actively penalized by the Q-Learning algorithm.
- **Context Tagging (IOMMU):** All P2P messages are cryptographically tagged with a Process ID (PID) granted by the DIANA Kernel. A malicious or misconfigured component cannot access restricted memory banks.
- **The "Dumb" Fallback:** If behavior is highly unpredictable (e.g., launching a novel application) and the Confidence Threshold drops below 80%, the SYNAPSE aborts predictive fetching. The OS gracefully falls back to classical CPU control until the behavior is learned. 

## Current Implementation Status
We are currently validating the DIANA concept entirely in software via Kernel-level Emulation inside a custom Linux Kernel module (`diana_core.ko`).

### Setup Instructions (For WSL2 Development)

This repository includes a custom automated build system to compile a Microsoft-standard linux kernel to support the DIANA module architecture.

1. Ensure WSL2 is installed on your Windows machine with Ubuntu 24.04.
2. Clone this repository.
3. CD into the repository and run the full build script via WSL:
   ```bash
   wsl -d Ubuntu -e bash scripts/build_full.sh
   ```
   *Note: This will download the full kernel source to `~/wsl2-kernel`, install required dependencies (`cpio`, `dwarves`), and compile both the `bzImage` and the `diana_core.ko` module. This process takes approximately 15-20 minutes on a standard 8-core CPU.*

4. Once compiled, run the QEMU boot wrapper to launch the DIANA virtual environment.
   ```bash
   bash scripts/run_qemu.sh
   ```

## Repository Structure

- `/kernel`: The `diana_core.ko` C source code. This acts as the Central Observer, utilizing kprobes to intercept kernel calls and measure real latencies.
- `/userspace/brain`: The PyTorch LSTM implementations and the Reinforcement Learning logic backend. 
- `/userspace/gui`: The futuristic web-based Desktop interface built in vanilla CSS and Javascript.
- `/scripts`: The isolated compilation environment scripts for building the kernel and booting QEMU.
