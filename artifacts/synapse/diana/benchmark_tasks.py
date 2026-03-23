"""
DIANA Phase 3 — Benchmark task definitions.

Each task describes a real-world workload as a list of WorkSteps.
The same task runs through both the Traditional and DIANA simulators
so results are directly comparable.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WorkStep:
    """One unit of work performed by a hardware component."""
    component: str      # "SSD", "GPU", "RAM"
    action: str         # human-readable description
    duration_ms: int    # simulated work duration


@dataclass
class BenchmarkTask:
    """A complete workload to benchmark under both architectures."""
    name: str
    icon: str
    description: str
    steps: list[WorkStep]
    cpu_overhead_ms: int = 50   # Traditional: permission round-trip per step
    diana_p2p_ms: int = 5       # DIANA: one-time peer sync handshake cost


# ──────────────────────────────────────────────────────────────────────
# Task 1 — Loading a game
# ──────────────────────────────────────────────────────────────────────
# Traditional: 12 sequential steps, each requiring a CPU round-trip.
# DIANA: SSD, GPU, RAM all start in parallel — no permission overhead.
#
# Traditional = 240ms work + 12 × 50ms overhead = 840ms
# DIANA       = max(SSD:90, GPU:85, RAM:65) + 5ms P2P = 95ms
# ──────────────────────────────────────────────────────────────────────

TASK_GAME = BenchmarkTask(
    name="Loading a game",
    icon="GAME",
    description="Boot a game: manifest parsing, asset loading, render init, memory allocation",
    steps=[
        # SSD pipeline (sequential on SSD, 90ms total)
        WorkStep("SSD", "Open game directory",         30),
        WorkStep("SSD", "Parse game manifest",         25),
        WorkStep("SSD", "Load core game files",        20),
        WorkStep("SSD", "Stream additional assets",    15),
        # GPU pipeline (sequential on GPU, 85ms total)
        WorkStep("GPU", "Verify driver and context",   25),
        WorkStep("GPU", "Initialize render pipeline",  20),
        WorkStep("GPU", "Load shader cache",           20),
        WorkStep("GPU", "Pre-render frame zero",       20),
        # RAM pipeline (sequential on RAM, 65ms total)
        WorkStep("RAM", "Allocate game heap",          20),
        WorkStep("RAM", "Cache scene graph",           20),
        WorkStep("RAM", "Map texture addresses",       15),
        WorkStep("RAM", "Index asset pointers",        10),
    ],
)

# ──────────────────────────────────────────────────────────────────────
# Task 2 — Opening a browser with 5 tabs
# ──────────────────────────────────────────────────────────────────────
# Traditional: 10 sequential steps, each requiring a CPU round-trip.
# DIANA: SSD, GPU, RAM work in parallel — GPU renders tabs concurrently.
#
# Traditional = 161ms work + 10 × 50ms overhead = 661ms
# DIANA       = max(SSD:42, GPU:71, RAM:48) + 5ms P2P = 76ms
# ──────────────────────────────────────────────────────────────────────

TASK_BROWSER = BenchmarkTask(
    name="Opening browser with 5 tabs",
    icon="BROWSER",
    description="Launch browser, fetch cached pages, render 5 tabs, allocate JS heaps",
    steps=[
        # SSD pipeline (42ms total)
        WorkStep("SSD", "Read browser profile cache",  15),
        WorkStep("SSD", "Fetch cached tab pages",      15),
        WorkStep("SSD", "Load extension manifests",    12),
        # GPU pipeline (71ms total — renders all 5 tabs)
        WorkStep("GPU", "Init compositor context",     20),
        WorkStep("GPU", "Rasterize tab 1 and 2",       18),
        WorkStep("GPU", "Rasterize tab 3 and 4",       18),
        WorkStep("GPU", "Rasterize tab 5 and chrome",  15),
        # RAM pipeline (48ms total)
        WorkStep("RAM", "Allocate JS heaps (×5)",      18),
        WorkStep("RAM", "Cache DOM trees",             15),
        WorkStep("RAM", "Index page resources",        15),
    ],
)

# ──────────────────────────────────────────────────────────────────────
# Task 3 — Running a video edit
# ──────────────────────────────────────────────────────────────────────
# Traditional: 14 sequential steps, each requiring a CPU round-trip.
# DIANA: GPU-heavy encode pipeline runs fully parallel with SSD I/O
#        and RAM buffer management — no CPU scheduling bottleneck.
#
# Traditional = 460ms work + 14 × 50ms overhead = 1160ms
# DIANA       = max(SSD:150, GPU:220, RAM:90) + 5ms P2P = 225ms
# ──────────────────────────────────────────────────────────────────────

TASK_VIDEO = BenchmarkTask(
    name="Running a video edit",
    icon="VIDEO",
    description="Import 4K footage, apply effects, encode timeline, export render",
    steps=[
        # SSD pipeline (150ms total — reading/writing 4K footage)
        WorkStep("SSD", "Import source footage",       40),
        WorkStep("SSD", "Read audio tracks",           35),
        WorkStep("SSD", "Load effect presets",         30),
        WorkStep("SSD", "Write render scratch files",  25),
        WorkStep("SSD", "Export final output",         20),
        # GPU pipeline (220ms total — heavy encode/decode)
        WorkStep("GPU", "Decode raw 4K frames",        55),
        WorkStep("GPU", "Apply color grade LUT",       50),
        WorkStep("GPU", "Apply motion blur effect",    45),
        WorkStep("GPU", "Encode H.264 output stream",  40),
        WorkStep("GPU", "Finalize render pipeline",    30),
        # RAM pipeline (90ms total — frame buffering)
        WorkStep("RAM", "Allocate frame buffer pool",  30),
        WorkStep("RAM", "Cache decoded frame ring",    25),
        WorkStep("RAM", "Swap encode input buffers",   20),
        WorkStep("RAM", "Flush output buffer to SSD",  15),
    ],
)

ALL_TASKS: list[BenchmarkTask] = [TASK_GAME, TASK_BROWSER, TASK_VIDEO]
