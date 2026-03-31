# DIANA-OS Honest Limitations

## Current Version (v0.1)

### What IS real in v0.1
*   **Kernel Hooks** — Linux module intercepts real CPU/memory calls (kmalloc, vf_read)
*   **SYNAPSE Frequency** — The kernel module learns real patterns
*   **P2P Bus** — Spinlocks route messages directly between components
*   **CPU Observer** — `commands_issued` is genuinely `0` at all times 
*   **LSTM Daemon** — Real PyTorch continuous training running in userspace
*   **`/proc/diana`** — Bridges kernel tables and userspace LSTM predictions
*   **Live UI** — The dashboard reads the kernel P2P log directly

### What IS NOT real yet in v0.1
*   **LSTM inside Kernel Space**
    *   *Why not*: The Linux kernel natively avoids floating-point mathematics for context-switch performance.
    *   *v0.1 Solution*: Offloads LSTM to userspace via `brain.py`, while using lightning-fast frequency tables inside the module itself.
    *   *Full Solution (Roadmap v0.2)*: Use eBPF Machine Learning hooks or custom built-in kernel float support.
*   **Direct Hardware Memory Control**
    *   *Why not*: The module hooks `__kmalloc`, but actual prefetching uses the kernel's existing memory mechanisms right now rather than directly controlling DIMM chips.
    *   *Full Solution (Roadmap v0.3)*: Custom memory controller driver.
*   **Direct GPU Hardware Control**
    *   *Why not*: We monitor GPU-related task switching right now, but writing a raw display driver requires deep hardware spec knowledge.
    *   *Full Solution (Roadmap v0.4)*: DRM/KMS driver integration with SYNAPSE.
*   **Physical P2P Motherboard Traces**
    *   *Why not*: This is software logic running on standard Von Neumann hardware.
    *   *Full Solution (Hardware Phase)*: A literal motherboard where the PCIe bus routes SSD data directly to RAM without waking the CPU socket at all.

---

## Roadmap to Full DIANA Architecture

*   **v0.1** — **(NOW)** Kernel hooks + Userspace LSTM
*   **v0.2** — eBPF ML hooks directly in kernel space
*   **v0.3** — Custom memory controller prefetching driver
*   **v0.4** — DRM/GPU complete bypass integration
*   **v0.5** — Complete Linux kernel fork (integrated natively, not as a module)
*   **v1.0** — Standalone DIANA-OS Distribution
