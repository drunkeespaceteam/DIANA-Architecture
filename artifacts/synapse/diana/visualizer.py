"""
DIANA Phase 4 — Real-Time Network Visualization Dashboard.

Replays the Phase 2 gaming scenario with live component state changes,
animated message flows, a live activity feed, and a final network map.
"""

from __future__ import annotations

import time
from collections import defaultdict

from synapse.core import SynapseChip

from .cpu_reporter import CPUReporter
from .viz_engine import (
    animate_message,
    print_activity_entry,
    print_communication_map,
    print_cpu_box,
    print_network_graph,
    print_section,
    print_state_change,
    print_thinking,
    print_viz_banner,
    BOLD, DIM, ITALIC, RESET, CYAN, GREEN, YELLOW, GREY,
)
from .display import COLOR


# ──────────────────────────────────────────────────────────────────────
# Training histories (same as Phase 2)
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
# Dashboard state tracker
# ──────────────────────────────────────────────────────────────────────

class Dashboard:
    """Tracks live state of all components and records the comm log."""

    def __init__(self) -> None:
        self.states: dict[str, str] = {"SSD": "IDLE", "GPU": "IDLE", "RAM": "IDLE"}
        self.cpu_msgs   = 0
        self.comm_log: list[dict]  = []
        self.activity_n = 0

    def set_state(self, component: str, state: str, reason: str = "") -> None:
        self.states[component] = state
        print_state_change(component, state, reason)

    def send_message(
        self,
        sender: str,
        receiver: str,
        content: str,
        msg_type: str,
        reasoning: str = "",
        speed: float = 0.025,
    ) -> None:
        """Animate a message transmission and record it."""
        self.activity_n += 1
        n = self.activity_n

        if receiver == "CPU":
            self.cpu_msgs += 1

        # Animate the flow
        animate_message(sender, receiver, content, msg_type, speed=speed)

        # Log for activity feed and final map
        self.comm_log.append({
            "n": n, "sender": sender, "receiver": receiver,
            "content": content, "type": msg_type, "reasoning": reasoning,
        })
        print_activity_entry(n, sender, receiver, content, msg_type, reasoning)

    def draw_graph(self, active_flows: list[tuple] | None = None) -> None:
        print_network_graph(self.states, self.cpu_msgs, active_flows)

    def draw_cpu_box(self) -> None:
        print_cpu_box(self.cpu_msgs)


# ──────────────────────────────────────────────────────────────────────
# Main visualization scenario
# ──────────────────────────────────────────────────────────────────────

def run_visualizer() -> None:
    d = Dashboard()

    # ── Header ────────────────────────────────────────────────────────
    print_viz_banner()

    # ── CPU initial status ────────────────────────────────────────────
    print_section("CPU REPORTER — PASSIVE OBSERVER")
    d.draw_cpu_box()
    time.sleep(0.3)

    # ── Initial network graph ─────────────────────────────────────────
    print_section("NETWORK GRAPH — INITIAL STATE  (all components IDLE)")
    d.draw_graph()
    time.sleep(0.4)

    # ── Training phase ────────────────────────────────────────────────
    print_section("INDEPENDENT LEARNING PHASE")

    chips: dict[str, SynapseChip] = {
        "SSD": SynapseChip(order=2),
        "GPU": SynapseChip(order=2),
        "RAM": SynapseChip(order=2),
    }
    training = {"SSD": SSD_TRAINING, "GPU": GPU_TRAINING, "RAM": RAM_TRAINING}

    for comp, seq in training.items():
        c = COLOR.get(comp, "")
        chips[comp].train(seq)
        s = chips[comp].summary()
        print(
            f"  {c}{BOLD}[{comp}]{RESET}  trained  "
            f"{DIM}{len(seq)} events → "
            f"{s['pattern_count']} patterns learned{RESET}"
        )
        time.sleep(0.15)

    print(f"\n  {DIM}Each chip is now ready to predict independently.{RESET}")
    time.sleep(0.3)

    # ── Simulation ────────────────────────────────────────────────────
    print_section("LIVE SIMULATION — Loading a game")
    print(f"  {DIM}Trigger: OS signals SSD — game executable launched.{RESET}\n")
    time.sleep(0.3)

    # ════════════════════════════════════════════════════════════════
    # STEP 1: SSD detects event
    # ════════════════════════════════════════════════════════════════
    print_section("STEP 1  ·  SSD detects game files loading")

    d.set_state("SSD", "ACTIVE", "OS event received")
    time.sleep(0.2)
    d.set_state("SSD", "PREDICTING")

    chips["SSD"].observe("game_files_load")
    pred = chips["SSD"].predict()
    conf = chips["SSD"].confidence()
    print_thinking(
        "SSD",
        f"game_files_load → '{pred}'  ({int(conf*100)}% confidence)"
    )
    time.sleep(0.2)

    d.set_state("SSD", "SENDING", "alerting GPU directly")
    d.draw_graph(active_flows=[("SSD", "GPU")])

    d.send_message(
        "SSD", "GPU",
        "game files loading — prepare to render",
        "alert",
        reasoning=f"learned: game_files_load → gpu_render  ({int(conf*100)}%)",
        speed=0.022,
    )

    d.send_message(
        "SSD", "CPU",
        "game files detected — scanning load pattern",
        "status",
    )
    d.set_state("SSD", "ACTIVE", "continuing file load")
    time.sleep(0.2)

    # ════════════════════════════════════════════════════════════════
    # STEP 2: GPU receives and responds
    # ════════════════════════════════════════════════════════════════
    print_section("STEP 2  ·  GPU processes SSD alert")

    d.set_state("GPU", "RECEIVING", "alert from SSD")
    time.sleep(0.2)
    d.set_state("GPU", "PREDICTING")

    chips["GPU"].observe("alert_received")
    gpu_pred = chips["GPU"].predict()
    gpu_conf = chips["GPU"].confidence()
    print_thinking(
        "GPU",
        f"alert_received → '{gpu_pred}'  ({int(gpu_conf*100)}% confidence)"
    )
    time.sleep(0.2)

    d.set_state("GPU", "SENDING", "responding to SSD")
    d.draw_graph(active_flows=[("GPU", "SSD")])

    d.send_message(
        "GPU", "SSD",
        "ready!",
        "ready",
        reasoning=f"learned: alert_received → respond_ready  ({int(gpu_conf*100)}%)",
        speed=0.018,
    )

    d.send_message(
        "GPU", "CPU",
        "alert received from SSD — spinning up render pipeline",
        "status",
    )
    d.set_state("GPU", "ACTIVE", "render pipeline spinning up")
    time.sleep(0.2)

    # ════════════════════════════════════════════════════════════════
    # STEP 3: RAM overhears GPU — reacts autonomously
    # ════════════════════════════════════════════════════════════════
    print_section("STEP 3  ·  RAM overhears GPU response — acts autonomously")
    print(
        f"  {DIM}RAM is subscribed to GPU's message stream (passive observer).{RESET}\n"
        f"  {DIM}RAM heard GPU say 'ready!' and draws its own conclusion.{RESET}\n"
    )
    time.sleep(0.25)

    d.set_state("RAM", "RECEIVING", "overheard GPU → SSD")
    time.sleep(0.2)
    d.set_state("RAM", "PREDICTING")

    chips["RAM"].observe("gpu_ready")
    ram_pred = chips["RAM"].predict()
    ram_conf = chips["RAM"].confidence()
    print_thinking(
        "RAM",
        f"gpu_ready → '{ram_pred}'  ({int(ram_conf*100)}% confidence)"
    )
    time.sleep(0.2)

    d.set_state("RAM", "SENDING", "proactively preloading")
    d.draw_graph(active_flows=[("RAM", "GPU")])

    d.send_message(
        "RAM", "GPU",
        "pre-loading game data into memory",
        "preload",
        reasoning=f"learned: gpu_ready → preload_game_data  ({int(ram_conf*100)}%)",
        speed=0.022,
    )

    d.send_message(
        "RAM", "CPU",
        "game data pre-loaded and ready",
        "status",
    )
    d.set_state("RAM", "ACTIVE", "memory buffers filling")
    time.sleep(0.2)

    # ════════════════════════════════════════════════════════════════
    # STEP 4: GPU acknowledges RAM
    # ════════════════════════════════════════════════════════════════
    print_section("STEP 4  ·  GPU acknowledges RAM pre-load")

    d.set_state("GPU", "SENDING", "acknowledging RAM")
    d.draw_graph(active_flows=[("GPU", "RAM")])

    d.send_message(
        "GPU", "RAM",
        "acknowledged — memory buffers accepted",
        "ready",
        reasoning="RAM acted unprompted — no controller needed",
        speed=0.018,
    )

    d.send_message(
        "GPU", "CPU",
        "render pipeline fully armed — frame 0 ready",
        "status",
    )
    d.set_state("GPU", "COMPLETE", "frame 0 queued")
    time.sleep(0.2)

    # ════════════════════════════════════════════════════════════════
    # STEP 5: SSD wraps up
    # ════════════════════════════════════════════════════════════════
    print_section("STEP 5  ·  SSD completes — notifies CPU only")

    chips["SSD"].observe("gpu_render")
    d.send_message(
        "SSD", "CPU",
        "task done — all game files transferred",
        "status",
    )
    d.set_state("SSD", "COMPLETE", "load sequence done")
    d.set_state("RAM", "COMPLETE", "buffers served")
    time.sleep(0.2)

    # ── Final network graph ───────────────────────────────────────────
    print_section("FINAL NETWORK STATE  (all components COMPLETE)")
    d.draw_graph()

    # ── Updated CPU box ───────────────────────────────────────────────
    print_section("CPU REPORTER — FINAL STATUS")
    d.draw_cpu_box()
    time.sleep(0.2)

    # ── Full activity feed replay ─────────────────────────────────────
    print_section("COMPLETE ACTIVITY FEED — ALL P2P MESSAGES")
    print()
    for entry in d.comm_log:
        print_activity_entry(
            entry["n"], entry["sender"], entry["receiver"],
            entry["content"], entry["type"], entry.get("reasoning", ""),
        )
        time.sleep(0.05)

    # ── Final communication map ───────────────────────────────────────
    print_communication_map(d.comm_log)
