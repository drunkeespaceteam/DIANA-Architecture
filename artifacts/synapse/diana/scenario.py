"""
DIANA Phase 2 — Gaming Scenario Simulation

Three independent SynapseChip instances communicate peer-to-peer:
  SSD Intelligence  — watches file I/O patterns
  GPU Intelligence  — watches render pipeline patterns
  RAM Intelligence  — watches memory access patterns

No central controller. The CPU Reporter is purely passive.
"""

from __future__ import annotations

import time

from .chip_node import ChipNode, clear_conversation, get_conversation
from .cpu_reporter import CPUReporter
from .display import (
    BOLD, DIM, ITALIC, RESET, COLOR, ARROW,
    chip_label, print_chip_thought, print_diana_header,
    print_divider, print_message,
)


# ──────────────────────────────────────────────────────────────────────
# Training histories — each chip trains independently
# ──────────────────────────────────────────────────────────────────────

SSD_TRAINING = [
    "idle", "game_files_load", "gpu_render", "idle",
    "idle", "game_files_load", "gpu_render", "idle",
    "game_files_load", "gpu_render",
    "game_files_load", "gpu_render",
    "idle", "game_files_load", "gpu_render", "idle",
    "asset_pack_load", "gpu_render",
    "game_files_load", "gpu_render",
]

GPU_TRAINING = [
    "standby", "alert_received", "respond_ready", "render_scene",
    "standby", "alert_received", "respond_ready", "render_scene",
    "alert_received", "respond_ready", "render_scene",
    "alert_received", "respond_ready", "render_scene",
    "standby", "alert_received", "respond_ready",
]

RAM_TRAINING = [
    "idle", "gpu_ready", "preload_game_data", "serving",
    "idle", "gpu_ready", "preload_game_data", "serving",
    "gpu_ready", "preload_game_data",
    "gpu_ready", "preload_game_data", "serving",
    "idle", "gpu_ready", "preload_game_data",
]


# ──────────────────────────────────────────────────────────────────────
# Section printer helpers
# ──────────────────────────────────────────────────────────────────────

def _section(title: str) -> None:
    print()
    print_divider(title)


def _pause() -> None:
    time.sleep(0.06)


# ──────────────────────────────────────────────────────────────────────
# Main simulation
# ──────────────────────────────────────────────────────────────────────

def run_diana_scenario() -> None:
    clear_conversation()

    print_diana_header()

    # ── 1. Instantiate the CPU Reporter ──────────────────────────────
    cpu = CPUReporter()

    # ── 2. Instantiate chip nodes ─────────────────────────────────────
    ssd = ChipNode("SSD", order=2, cpu=cpu)
    gpu = ChipNode("GPU", order=2, cpu=cpu)
    ram = ChipNode("RAM", order=2, cpu=cpu)

    # ── 3. Establish P2P connections (no central router) ─────────────
    _section("P2P NETWORK SETUP")
    ssd.connect(gpu)      # SSD ↔ GPU
    ssd.connect(ram)      # SSD ↔ RAM
    gpu.connect(ram)      # GPU ↔ RAM

    for node in (ssd, gpu, ram):
        peers = ", ".join(node.peers)
        print(f"  {chip_label(node.name)}  peers: {peers}")

    # ── 4. RAM subscribes to GPU messages (passive eavesdropping) ─────
    ram.subscribe(gpu)    # RAM silently hears everything GPU receives
    print(f"\n  {chip_label('RAM')} subscribes to {chip_label('GPU')} "
          f"{DIM}(passive observer — no control){RESET}")

    # ── 5. Training phase ─────────────────────────────────────────────
    _section("INDEPENDENT LEARNING PHASE")
    print(f"\n  Each chip trains on its own historical task stream.\n")

    ssd.train(SSD_TRAINING)
    print(f"  {chip_label('SSD')}  trained on {len(SSD_TRAINING)} I/O events  "
          f"→  {ssd.chip.summary()['pattern_count']} patterns learned")
    _pause()

    gpu.train(GPU_TRAINING)
    print(f"  {chip_label('GPU')}  trained on {len(GPU_TRAINING)} render events  "
          f"→  {gpu.chip.summary()['pattern_count']} patterns learned")
    _pause()

    ram.train(RAM_TRAINING)
    print(f"  {chip_label('RAM')}  trained on {len(RAM_TRAINING)} memory events  "
          f"→  {ram.chip.summary()['pattern_count']} patterns learned")
    _pause()

    # ── 6. Simulation ─────────────────────────────────────────────────
    _section("LIVE P2P SIMULATION")
    print(
        f"\n  {DIM}Trigger: OS signals SSD — game executable launched.{RESET}\n"
    )

    # ── Step 1: SSD observes game file load ───────────────────────────
    _section("STEP 1  ·  SSD detects game files loading")
    ssd_event = "game_files_load"
    prediction = ssd.observe_event(ssd_event)
    conf = ssd.chip.confidence()

    print_chip_thought(
        "SSD",
        f"observed '{ssd_event}'  →  predicts next: '{prediction}'  "
        f"(confidence {int(conf * 100)}%)"
    )
    ssd.broadcast_status("game files detected — scanning load pattern")
    _pause()

    # SSD intelligence decides to alert GPU directly
    reasoning_ssd = (
        f"learned: game_files_load → gpu_render  "
        f"({int(conf * 100)}% confidence)"
    )
    alert_content = "game files loading — prepare to render"
    print()
    print_message("SSD", "GPU", alert_content, "alert", reasoning_ssd)
    ssd.send("GPU", alert_content, msg_type="alert", reasoning=reasoning_ssd)
    _pause()

    # ── Step 2: GPU receives alert, consults its own chip ─────────────
    _section("STEP 2  ·  GPU processes SSD alert")
    gpu_event = "alert_received"
    gpu_prediction = gpu.observe_event(gpu_event)
    gpu_conf = gpu.chip.confidence()

    print_chip_thought(
        "GPU",
        f"observed '{gpu_event}'  →  predicts next: '{gpu_prediction}'  "
        f"(confidence {int(gpu_conf * 100)}%)"
    )
    gpu.broadcast_status("alert received from SSD — spinning up render pipeline")
    _pause()

    # GPU responds ready directly to SSD
    reasoning_gpu = (
        f"learned: alert_received → respond_ready  "
        f"({int(gpu_conf * 100)}% confidence)"
    )
    ready_content = "ready!"
    print()
    print_message("GPU", "SSD", ready_content, "ready", reasoning_gpu)
    gpu.send("SSD", ready_content, msg_type="ready", reasoning=reasoning_gpu)
    _pause()

    # ── Step 3: RAM overhears GPU's ready signal ─────────────────────
    _section("STEP 3  ·  RAM overhears GPU — reacts autonomously")
    print(
        f"  {chip_label('RAM')} {DIM}(subscribed observer) — "
        f"heard GPU sent 'ready!'{RESET}\n"
    )

    ram_event = "gpu_ready"
    ram_prediction = ram.observe_event(ram_event)
    ram_conf = ram.chip.confidence()

    print_chip_thought(
        "RAM",
        f"observed '{ram_event}'  →  predicts next: '{ram_prediction}'  "
        f"(confidence {int(ram_conf * 100)}%)"
    )
    _pause()

    # RAM proactively preloads game data into memory
    reasoning_ram = (
        f"learned: gpu_ready → preload_game_data  "
        f"({int(ram_conf * 100)}% confidence)"
    )
    preload_content = "pre-loading game data into memory"
    print()
    print_message("RAM", "GPU", preload_content, "preload", reasoning_ram)
    ram.send("GPU", preload_content, msg_type="preload", reasoning=reasoning_ram)
    ram.broadcast_status("game data pre-loaded and ready")
    _pause()

    # ── Step 4: GPU acknowledges RAM ──────────────────────────────────
    _section("STEP 4  ·  GPU acknowledges RAM pre-load")
    gpu.observe_event("respond_ready")
    ack_content = "acknowledged — memory buffers accepted"
    reasoning_ack = "RAM pre-loaded data unprompted — no controller needed"
    print_message("GPU", "RAM", ack_content, "ready", reasoning_ack)
    gpu.send("RAM", ack_content, msg_type="ready", reasoning=reasoning_ack)
    gpu.broadcast_status("render pipeline fully armed — frame 0 ready")
    _pause()

    # ── Step 5: SSD wraps up ─────────────────────────────────────────
    _section("STEP 5  ·  SSD completes load, notifies CPU")
    ssd.observe_event("gpu_render")
    ssd.broadcast_status("task done — all game files transferred")
    print(
        f"  {chip_label('SSD')} {DIM}completes load sequence. "
        f"CPU informed via status log only.{RESET}"
    )

    # ── Full conversation replay ──────────────────────────────────────
    _section("FULL P2P CONVERSATION LOG")
    print()
    for msg in get_conversation():
        if msg.msg_type == "observe":
            sc = COLOR.get(msg.sender, "")
            print(
                f"  {sc}{BOLD}{msg.sender:<4}{RESET} "
                f"{DIM}overheard:{RESET}  {msg.content}"
            )
        else:
            print_message(
                msg.sender, msg.receiver,
                msg.content, msg.msg_type,
                msg.reasoning,
            )
        _pause()

    # ── CPU Reporter final log ────────────────────────────────────────
    _section("CPU REPORTER — PASSIVE STATUS LOG")
    print(
        f"\n  {DIM}CPU received only status updates. "
        f"It issued zero commands.{RESET}"
    )
    cpu.print_report()

    # ── Summary ───────────────────────────────────────────────────────
    _section("DIANA ARCHITECTURE SUMMARY")
    print()
    for node in (ssd, gpu, ram):
        s = node.summary()
        print(
            f"  {chip_label(node.name)}  "
            f"tasks observed: {s['tasks_observed']}  ·  "
            f"patterns: {s['pattern_count']}  ·  "
            f"peers: {', '.join(s['peers'])}"
        )
    print()
    print(
        f"  {DIM}No central controller was used. "
        f"All decisions emerged from independent chip intelligence.{RESET}"
    )
    print()
