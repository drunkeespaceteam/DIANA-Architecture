"""
DIANA Phase 6 — LSTM + RL simulation runner.

Scenario: Game Engine Memory Trace
────────────────────────────────────
Three hardware components (RAM, GPU, SSD) each receive a memory access
trace from a running 3D game engine.  Every component's embedded LSTM
learns the access patterns online.  The RL agent decides when to
pre-fetch the predicted address.  The CPU observes but never commands.

Memory access patterns:
  GPU  — render pipeline loop: vtx_0 → vtx_1 → vtx_2 → tex_0 → tex_1 → draw
  SSD  — sequential block reads: blk_0 → blk_1 → blk_2 → blk_3 → (repeat)
  RAM  — mixed access: ram_0 → ram_1 → ram_2 → ram_3 → (repeat)

The simulation is divided into four epochs:
  Epoch 1 (Warm-up):   LSTM has no training; predictions are near-random.
  Epoch 2 (Learning):  LSTM begins recognising the repeating pattern.
  Epoch 3 (Improving): Confidence rises; RL starts choosing PREFETCH.
  Epoch 4 (Converged): High accuracy; RL exploits confident predictions.
"""

from __future__ import annotations

import time
from collections import defaultdict

from .component import Component, CPUObserver
from .p2p_bus import P2PBus

from .phase6_display import (
    BOLD, DIM, RESET, CYAN, GREEN, YELLOW, RED, MAGENTA, ORANGE,
    BLUE, TEAL, COMP_COLOR, W,
    _section, _thin, _sleep, _acc_bar, _box_line, _box_top, _box_bot, _box_div,
    print_banner,
    print_architecture,
    print_step,
    print_epoch_scorecard,
    print_bus_log,
    print_rl_progress,
    print_accuracy_chart,
    print_final_summary,
    print_proof,
)


# ──────────────────────────────────────────────────────────────────────
# Memory access traces
# ──────────────────────────────────────────────────────────────────────

GPU_VOCAB = ["vtx_0", "vtx_1", "vtx_2", "tex_0", "tex_1", "draw_0"]
SSD_VOCAB = ["blk_0", "blk_1", "blk_2", "blk_3", "seek_A", "seek_B"]
RAM_VOCAB = ["ram_0", "ram_1", "ram_2", "ram_3", "bus_A",  "bus_B" ]

# 40-event traces (mostly repeating with a few variations for realism)
GPU_TRACE = (
    ["vtx_0", "vtx_1", "vtx_2", "tex_0", "tex_1", "draw_0"] * 5    # frames 1-5
  + ["vtx_0", "vtx_1", "vtx_2", "tex_0", "tex_1", "draw_0"] * 2    # frames 6-7 (converge)
  + ["vtx_0", "vtx_1", "vtx_2", "tex_0"]                            # partial frame
)[:42]

SSD_TRACE = (
    ["blk_0", "blk_1", "blk_2", "blk_3"] * 8                        # sequential reads
  + ["seek_A", "blk_0", "seek_B", "blk_2"]                          # random seeks
  + ["blk_0", "blk_1", "blk_2", "blk_3"] * 2                        # back to sequential
)[:42]

RAM_TRACE = (
    ["ram_0", "ram_1", "ram_2", "ram_3"] * 9                         # simple loop
  + ["bus_A", "bus_B", "ram_0", "ram_1"]                             # bus traffic
  + ["ram_0", "ram_1"]
)[:42]

# Epoch slice boundaries (indices into trace, 0-based)
EPOCHS = [
    ("Warm-up",   0,  10),    # steps 1-10
    ("Learning",  10, 20),    # steps 11-20
    ("Improving", 20, 30),    # steps 21-30
    ("Converged", 30, 42),    # steps 31-42
]

# How many individual steps to display verbosely per epoch
VERBOSE_PER_EPOCH = 4


# ──────────────────────────────────────────────────────────────────────
# Build system
# ──────────────────────────────────────────────────────────────────────

def _build_system() -> tuple[list[Component], CPUObserver, P2PBus]:
    cpu = CPUObserver()
    bus = P2PBus()

    components = [
        Component("GPU", GPU_VOCAB, bus, cpu, embed_dim=8, hidden=16, window=4),
        Component("SSD", SSD_VOCAB, bus, cpu, embed_dim=8, hidden=16, window=4),
        Component("RAM", RAM_VOCAB, bus, cpu, embed_dim=8, hidden=16, window=4),
    ]
    for comp in components:
        bus.register(comp)

    return components, cpu, bus


TRACES = {"GPU": GPU_TRACE, "SSD": SSD_TRACE, "RAM": RAM_TRACE}


# ──────────────────────────────────────────────────────────────────────
# Main runner
# ──────────────────────────────────────────────────────────────────────

def run_phase6() -> None:
    components, cpu, bus = _build_system()

    # ── Banner ────────────────────────────────────────────────────────
    print_banner()
    _sleep(0.3)

    # ── Architecture overview ─────────────────────────────────────────
    print_architecture(components, bus)

    # ── Trace introduction ────────────────────────────────────────────
    _section("MEMORY ACCESS TRACES")
    print(f"  {DIM}Each component receives a 42-event game-engine memory trace.{RESET}")
    print(f"  {DIM}Patterns are initially unknown; the LSTM learns them online.{RESET}\n")

    for comp in components:
        c = COMP_COLOR.get(comp.name, "")
        trace = TRACES[comp.name]
        pattern = " → ".join(trace[:6]) + "  …  (×7)"
        print(f"  {c}{BOLD}[{comp.name}]{RESET}  {DIM}{pattern}{RESET}")
        _sleep(0.08)

    print()
    _sleep(0.3)

    # ── Per-epoch step tracking ────────────────────────────────────────
    comp_epoch_accs: dict[str, list[float]] = {c.name: [] for c in components}
    epoch_labels: list[str] = []

    # ── Epoch simulation loop ─────────────────────────────────────────
    for epoch_n, (label, start, end) in enumerate(EPOCHS, 1):

        _section(f"EPOCH {epoch_n}  ·  {label.upper()}  [steps {start+1}–{end}]")

        if epoch_n == 1:
            print(
                f"  {DIM}LSTM is untrained — predictions are near-random.{RESET}\n"
                f"  {DIM}RL is exploring with ε={components[0].rl.epsilon:.2f}.{RESET}\n"
            )
        elif epoch_n == 2:
            print(
                f"  {DIM}LSTM has seen {start} examples — patterns beginning to emerge.{RESET}\n"
                f"  {DIM}RL is adapting its pre-fetch policy.{RESET}\n"
            )
        elif epoch_n == 3:
            print(
                f"  {DIM}LSTM confidence rising — RL switching from WAIT to PREFETCH.{RESET}\n"
            )
        else:
            print(
                f"  {DIM}LSTM has converged — RL exploiting high-confidence predictions.{RESET}\n"
            )

        # Per-epoch stats trackers
        epoch_hits: dict[str, int] = {c.name: 0 for c in components}
        epoch_total: dict[str, int] = {c.name: 0 for c in components}
        epoch_pf:    dict[str, int] = {c.name: 0 for c in components}

        verbose_count = 0
        bus_log_before = bus.message_count

        for step_idx in range(start, end):
            # Run one step on each component
            recs = []
            for comp in components:
                trace = TRACES[comp.name]
                event = trace[step_idx]
                rec = comp.observe(event)
                recs.append(rec)

                # Accumulate epoch stats
                if rec.hit is not None:
                    epoch_total[comp.name] += 1
                    if rec.hit:
                        epoch_hits[comp.name] += 1
                if rec.action == "PREFETCH":
                    epoch_pf[comp.name] += 1

            # Print detailed output for first VERBOSE_PER_EPOCH steps per epoch
            if verbose_count < VERBOSE_PER_EPOCH:
                for rec in recs:
                    print_step(rec, verbose=(epoch_n >= 2))
                if verbose_count == 0 and epoch_n == 1:
                    print(
                        f"\n  {DIM}LSTM has no prior training — "
                        f"predictions are essentially random{RESET}\n"
                    )
                verbose_count += 1
                _sleep(0.05)

        # Print a "…" separator if we skipped steps
        remaining = (end - start) - VERBOSE_PER_EPOCH
        if remaining > 0:
            print(
                f"  {DIM}  … {remaining} more steps — "
                f"LSTM training in progress …{RESET}\n"
            )

        # P2P bus messages this epoch
        new_bus_msgs = bus.message_count - bus_log_before
        if new_bus_msgs > 0:
            print(
                f"  {MAGENTA}{BOLD}P2P Bus:{RESET}  "
                f"{new_bus_msgs} pre-fetch requests broadcast this epoch "
                f"(zero CPU hops)\n"
            )

        # Epoch scorecard
        epoch_stats = [
            {
                "name":             comp.name,
                "epoch_hits":       epoch_hits[comp.name],
                "epoch_total":      epoch_total[comp.name],
                "epoch_prefetches": epoch_pf[comp.name],
            }
            for comp in components
        ]
        print_epoch_scorecard(epoch_n, label, epoch_stats)

        # Record per-epoch accuracy for the chart
        epoch_labels.append(f"Ep{epoch_n}")
        for comp in components:
            tot  = epoch_total[comp.name]
            hits = epoch_hits[comp.name]
            comp_epoch_accs[comp.name].append(hits / tot if tot else 0.0)

        # RL progress after each epoch
        _section(f"RL AGENT STATUS  (after epoch {epoch_n})")
        for comp in components:
            print_rl_progress(comp, [])
        print()
        _sleep(0.1)

    # ── P2P Bus log (sample) ──────────────────────────────────────────
    print_bus_log(bus, max_entries=12)

    # ── Accuracy chart ─────────────────────────────────────────────────
    print_accuracy_chart(epoch_labels, comp_epoch_accs)

    # ── CPU Observer report ────────────────────────────────────────────
    _section("CPU OBSERVER REPORT")
    cpu_r = cpu.report()
    print(
        f"  {COMP_COLOR['CPU']}{BOLD}CPU{RESET}  "
        f"status updates received: {YELLOW}{cpu_r['total_updates']}{RESET}\n"
        f"  {DIM}Senders: {', '.join(cpu_r['senders'])}{RESET}\n"
        f"  Commands issued: {GREEN}{BOLD}0{RESET}  "
        f"{DIM}← CPU was passive observer throughout{RESET}\n"
    )
    _sleep(0.15)

    # ── Final summary ─────────────────────────────────────────────────
    print_final_summary(components, cpu, bus)

    # ── Proof statements ──────────────────────────────────────────────
    print_proof(components)
