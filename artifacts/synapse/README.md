# DIANA Architecture — SYNAPSE Chip Simulation

> *Distributed Intelligence Architecture for Networked Autonomy*

A Python simulation of an intelligent hardware chip ecosystem where components learn patterns, predict future operations, and communicate peer-to-peer — without ever asking the CPU for permission.

---

## What is DIANA?

DIANA (**D**istributed **I**ntelligence **A**rchitecture for **N**etworked **A**utonomy) is a theoretical chip architecture where every hardware component — SSD, GPU, RAM — is embedded with its own intelligence layer.

Instead of waiting for the CPU to schedule every read, write, and render operation, each component:

- **Watches** its own activity stream for recurring patterns
- **Predicts** what it will be asked to do next (before the request arrives)
- **Communicates directly** with peer components via P2P messaging
- **Acts proactively** — preloading data, spinning up pipelines, reserving buffers

The CPU becomes a **passive observer**. It receives status reports. It never issues commands.

---

## What Problem Does It Solve?

Modern computers suffer from a fundamental bottleneck: **every component must route all requests through the CPU**.

```
SSD wants to pre-load files?     → Ask CPU first.
GPU wants to spin up a render?   → Ask CPU first.
RAM wants to reserve a buffer?   → Ask CPU first.
```

This creates:

- **Sequential execution** — operations that could run in parallel wait in line
- **CPU interrupt storms** — hundreds of context switches per second for routine I/O
- **Wasted latency** — 50ms+ permission round-trips before any real work begins
- **CPU as a single point of failure** — one bottleneck controls everything

DIANA eliminates the permission bottleneck entirely. Components develop their own intelligence, form a peer mesh, and self-coordinate. The CPU is informed — never queried.

---

## The 4 Phases

### Phase 1 — The SYNAPSE Core Chip

A single intelligent chip that learns task sequences using **n-gram pattern recognition** (Markov chain analysis).

- Observes a stream of task events
- Builds a frequency table of which tasks follow which
- Predicts the next task with a confidence score
- Supports n-gram orders 1–5 (configurable context window)
- Falls back to shorter context if the full window is unseen

```bash
python main.py --demo          # run built-in learning demo
python main.py                 # interactive REPL
python main.py --tasks "A,B,A,B,A"
python main.py --order 3 --tasks "A,B,C,A,B,C,A,B"
```

**Core API:**

```python
from synapse import SynapseChip

chip = SynapseChip(order=2)
chip.train(["game_load", "gpu_render", "game_load", "gpu_render"])
chip.observe("game_load")
chip.predict()      # → "gpu_render"
chip.confidence()   # → 1.0
```

**Test suite:** 11 unit tests covering prediction, confidence, fallback, save/load, and edge cases.

---

### Phase 2 — DIANA P2P Multi-Chip Architecture

Three independent SynapseChip instances — one embedded in each hardware component — form a peer-to-peer mesh network.

| Component | Role | Trains on |
|-----------|------|-----------|
| **SSD**   | Detects file-load patterns, alerts GPU | File I/O event stream |
| **GPU**   | Responds to SSD alerts, spins up render pipeline | Render request patterns |
| **RAM**   | Overhears GPU readiness, proactively pre-loads data | Memory allocation patterns |
| **CPU**   | Passive reporter only | *(receives status, sends nothing)* |

```bash
python main.py --diana
```

**No central controller.** All decisions emerge from each chip's learned model. The CPU is copied on status updates — it never initiates a command.

---

### Phase 3 — Benchmarking Engine

A simulation engine that runs identical workloads through both the Traditional (CPU-gated) and DIANA (P2P autonomous) architectures, then produces a detailed comparison report.

```bash
python main.py --benchmark
```

**How it works:**

- **Traditional model:** Every step must first request CPU permission (50ms round-trip overhead), then execute sequentially. Total time = Σ(work) + N × 50ms.
- **DIANA model:** All components start simultaneously, each running their own task queue in parallel. Total time = max(component queues) + 5ms P2P handshake.

**Benchmark Results:**

| Task | Traditional | DIANA | Speedup |
|------|-------------|-------|---------|
| Loading a game | 840ms | 95ms | **8.8×** |
| Opening browser (5 tabs) | 661ms | 76ms | **8.7×** |
| Running a video edit | 1,160ms | 225ms | **5.2×** |
| **Total** | **2,661ms** | **396ms** | **6.72×** |

**Additional metrics:**

- CPU interrupt reduction: **100%** (36 interrupts → 0)
- Total time saved across all tasks: **2,265ms**
- Wall-clock efficiency gain: **85.1%**
- DIANA Architecture Score: **80 / 100**

> The video edit scores lower (5.2×) because its GPU encode pipeline is genuinely serial — DIANA removes all waiting overhead but cannot speed up inherently sequential GPU work. This is an honest result.

---

### Phase 4 — Real-Time Visualization Dashboard

A terminal-based live visualization dashboard that replays the Phase 2 gaming scenario with animated graphics.

```bash
python main.py --visualize
```

**What it shows:**

1. **Network graph** — ASCII art triangle mesh of SSD, GPU, and RAM components with the CPU passive observer at the top. Connection lines turn amber when a message flows through them.

2. **Animated message flows** — Each P2P message is shown transmitting across a live progress bar:
   ```
   SSD ══[ALERT ]══▶ GPU  "game files loading — prepare to render"
     transmitting  [▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░] 46%
     delivered      [▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓] SENT ✓
   ```

3. **Component status indicators** — Each component transitions through states in real time:
   ```
   ○ IDLE  →  ◉ ACTIVE  →  ◈ PREDICTING  →  ▶ SENDING  →  ✓ COMPLETE
   ```

4. **Live activity feed** — Numbered log of every P2P message, with the n-gram reasoning that triggered it.

5. **CPU passive proof** — CPU message count updates live (status reports received), while commands issued stays permanently at **0**.

6. **Final network communication map** — A From/To matrix showing which component talked to which, how many times, with per-component send/receive bars and message type breakdown.

---

## Project Structure

```
artifacts/synapse/
├── main.py                      # CLI entry point (--demo, --diana, --benchmark, --visualize)
├── README.md                    # This file
├── synapse/
│   ├── core.py                  # SynapseChip — n-gram engine
│   ├── display.py               # Console output helpers
│   └── repl.py                  # Interactive REPL
├── diana/
│   ├── chip_node.py             # ChipNode — P2P messaging layer
│   ├── cpu_reporter.py          # CPUReporter — passive observer
│   ├── scenario.py              # Phase 2 gaming scenario
│   ├── benchmark_tasks.py       # Workload definitions (3 tasks × 3 components)
│   ├── benchmark_engine.py      # Traditional and DIANA simulation models
│   ├── benchmark_display.py     # Benchmark report renderer
│   ├── benchmark.py             # Phase 3 entry point
│   ├── viz_engine.py            # Phase 4 rendering primitives
│   ├── visualizer.py            # Phase 4 dashboard scenario runner
│   └── display.py               # Shared ANSI colour constants
└── tests/
    └── test_synapse.py          # 11 unit tests
```

---

## Quick Start

```bash
# Phase 1 — Core chip demo
python main.py --demo

# Phase 2 — P2P multi-chip simulation
python main.py --diana

# Phase 3 — Architecture benchmark
python main.py --benchmark

# Phase 4 — Live visualization dashboard
python main.py --visualize

# Interactive REPL
python main.py

# Run tests
python tests/test_synapse.py
```

---

## Design Principles

- **No external dependencies** — pure Python standard library throughout
- **No mocking** — every metric is computed from the simulation model, not hardcoded
- **Honest benchmarking** — results reflect the actual architecture constraints (e.g. video edit scores lower because GPU work is inherently serial)
- **Mobile-friendly terminal output** — all visuals use ANSI escape codes only, no curses or full-screen TUI

---

## Author

**Sahidh**

DIANA Architecture — SYNAPSE Chip Simulation
