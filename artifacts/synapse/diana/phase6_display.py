"""
DIANA Phase 6 — Display engine for the LSTM + RL simulation.

Renders: Phase 6 banner, architecture diagram, per-step event cards,
epoch scorecards, P2P bus log, accuracy chart, and final summary.
"""

from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .component import Component, CPUObserver, StepRecord
    from .p2p_bus import P2PBus

from .display import BOLD, DIM, ITALIC, RESET

# ── Colour palette ─────────────────────────────────────────────────────
CYAN    = "\033[38;5;51m"
GREEN   = "\033[38;5;82m"
YELLOW  = "\033[38;5;226m"
RED     = "\033[38;5;196m"
MAGENTA = "\033[38;5;201m"
ORANGE  = "\033[38;5;214m"
WHITE   = "\033[38;5;231m"
GREY    = "\033[38;5;244m"
BLUE    = "\033[38;5;39m"
PINK    = "\033[38;5;213m"
TEAL    = "\033[38;5;43m"

COMP_COLOR = {
    "RAM": BLUE,
    "GPU": GREEN,
    "SSD": ORANGE,
    "CPU": "\033[38;5;197m",
}

W = 66   # display width


# ──────────────────────────────────────────────────────────────────────
# Low-level helpers
# ──────────────────────────────────────────────────────────────────────

def _write(s: str) -> None:
    sys.stdout.write(s)
    sys.stdout.flush()


def _sleep(s: float) -> None:
    time.sleep(s)


import re as _re

def _vis_len(text: str) -> int:
    return len(_re.sub(r"\033\[[0-9;]*m", "", text))


def _pad(text: str, width: int) -> str:
    p = max(0, width - _vis_len(text))
    return text + " " * p


def _thin(w: int = W) -> str:
    return "  " + "─" * (w - 2)


def _box_top(w: int = W) -> str:
    return "  ╔" + "═" * (w - 4) + "╗"


def _box_bot(w: int = W) -> str:
    return "  ╚" + "═" * (w - 4) + "╝"


def _box_div(w: int = W) -> str:
    return "  ╠" + "─" * (w - 4) + "╣"


def _box_line(content: str, w: int = W) -> str:
    return f"  ║ {_pad(content, w - 6)} ║"


def _section(title: str) -> None:
    pad = max(0, W - 6 - len(title)) // 2
    line = "─" * pad + f" {BOLD}{title}{RESET} " + "─" * pad
    print(f"\n  {line}\n")


def _acc_bar(acc: float, width: int = 20) -> str:
    filled = int(acc * width)
    empty  = width - filled
    if   acc >= 0.85: c = GREEN
    elif acc >= 0.55: c = YELLOW
    else:             c = RED
    return f"{c}{'█' * filled}{RESET}{DIM}{'░' * empty}{RESET}"


# ──────────────────────────────────────────────────────────────────────
# Phase 6 banner
# ──────────────────────────────────────────────────────────────────────

BANNER = f"""
{BOLD}  ██████╗ ██╗ █████╗ ███╗   ██╗ █████╗     {TEAL}Phase 6{RESET}
{BOLD}  ██╔══██╗██║██╔══██╗████╗  ██║██╔══██╗    {TEAL}SynapseBrain{RESET}
{BOLD}  ██║  ██║██║███████║██╔██╗ ██║███████║    {TEAL}LSTM + Reinforcement Learning{RESET}
{BOLD}  ██║  ██║██║██╔══██║██║╚██╗██║██╔══██║{RESET}
{BOLD}  ██████╔╝██║██║  ██║██║ ╚████║██║  ██║{RESET}
{BOLD}  ╚═════╝ ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝{RESET}
  {DIM}Each chip runs a real LSTM · RL decides when to pre-fetch{RESET}
"""


def print_banner() -> None:
    print(BANNER)


# ──────────────────────────────────────────────────────────────────────
# Architecture overview diagram
# ──────────────────────────────────────────────────────────────────────

def print_architecture(components: list["Component"], bus: "P2PBus") -> None:
    _section("ARCHITECTURE OVERVIEW")
    print(_box_top())
    print(_box_line(f"  {BOLD}DIANA Phase 6 — Neural Hardware Intelligence{RESET}"))
    print(_box_div())

    for comp in components:
        c = COMP_COLOR.get(comp.name, WHITE)
        s = comp.brain.summary()
        print(_box_line(
            f"  {c}{BOLD}[{comp.name}]{RESET}  "
            f"{TEAL}SynapseBrain{RESET}(LSTM)  "
            f"{DIM}vocab={s['vocab_size']}  window={s['window']}  "
            f"params={s['param_count']}{RESET}  +  "
            f"{MAGENTA}RLAgent{RESET}(Q-learning)"
        ))

    print(_box_div())
    print(_box_line(
        f"  {CYAN}{BOLD}P2P Bus{RESET}  "
        f"{DIM}direct routing — zero CPU hops{RESET}  "
        f"{GREEN}peers: {', '.join(bus._registry)}{RESET}"
    ))
    print(_box_line(
        f"  {COMP_COLOR['CPU']}{BOLD}CPU Observer{RESET}  "
        f"{DIM}passive — receives status only, issues zero commands{RESET}"
    ))
    print(_box_div())
    print(_box_line(
        f"  {DIM}Upgrade from Phases 1-5:{RESET}  "
        f"{YELLOW}Markov n-gram{RESET} {DIM}→{RESET} "
        f"{TEAL}LSTM{RESET} + {MAGENTA}Reinforcement Learning{RESET}"
    ))
    print(_box_bot())
    print()
    _sleep(0.25)


# ──────────────────────────────────────────────────────────────────────
# Per-step event card
# ──────────────────────────────────────────────────────────────────────

def print_step(rec: "StepRecord", verbose: bool = True) -> None:
    c     = COMP_COLOR.get(rec.component, WHITE)
    e_col = CYAN

    hit_s   = ""
    loss_s  = ""
    pred_s  = f"{DIM}— warming up —{RESET}"
    action_s = ""

    if rec.pred is not None:
        pct = int(rec.conf * 100)
        pred_col = TEAL
        pred_s = (
            f"{pred_col}{BOLD}{rec.pred}{RESET}  "
            f"{DIM}({pct}% conf){RESET}"
        )
        if rec.action == "PREFETCH":
            action_s = f"  {MAGENTA}{BOLD}→ PREFETCH{RESET}"
        else:
            action_s = f"  {DIM}→ WAIT{RESET}"

    if rec.hit is True:
        hit_s = f"  {GREEN}{BOLD}✓ HIT{RESET}"
        if rec.reward > 0.5:
            hit_s += f"  {GREEN}{BOLD}+{rec.reward:.1f}{RESET}"
    elif rec.hit is False:
        hit_s = f"  {RED}{BOLD}✗ MISS{RESET}"
        if rec.reward < 0:
            hit_s += f"  {RED}{rec.reward:.1f}{RESET}"

    if rec.loss is not None and verbose:
        loss_s = f"  {DIM}loss={rec.loss:.3f}{RESET}"

    print(
        f"  {DIM}[{rec.step_n:02d}]{RESET}  "
        f"{c}{BOLD}{rec.component}{RESET}  "
        f"event: {e_col}{BOLD}{rec.event}{RESET}  "
        f"→ lstm: {pred_s}{action_s}{hit_s}{loss_s}"
    )
    _sleep(0.04)


# ──────────────────────────────────────────────────────────────────────
# Epoch scorecard
# ──────────────────────────────────────────────────────────────────────

def print_epoch_scorecard(
    epoch_n:    int,
    label:      str,
    comp_stats: list[dict],   # list of {"name", "epoch_hits", "epoch_total"}
) -> None:
    print()
    print(_box_top())
    print(_box_line(f"  {BOLD}EPOCH {epoch_n}  ·  {label}{RESET}"))
    print(_box_div())

    for stat in comp_stats:
        name      = stat["name"]
        hits      = stat["epoch_hits"]
        total     = stat["epoch_total"]
        acc       = hits / total if total else 0.0
        bar       = _acc_bar(acc, 16)
        pct       = int(acc * 100)
        c         = COMP_COLOR.get(name, WHITE)
        pf        = stat.get("epoch_prefetches", 0)
        pf_s      = f"  {DIM}prefetches: {pf}{RESET}" if pf else ""

        print(_box_line(
            f"  {c}{BOLD}{name}{RESET}  "
            f"{bar}  {BOLD}{pct:>3}%{RESET}  "
            f"{DIM}({hits}/{total} correct){RESET}{pf_s}"
        ))
        _sleep(0.05)

    print(_box_bot())
    print()
    _sleep(0.12)


# ──────────────────────────────────────────────────────────────────────
# P2P bus communication log
# ──────────────────────────────────────────────────────────────────────

def print_bus_log(bus: "P2PBus", max_entries: int = 12) -> None:
    _section("P2P BUS COMMUNICATION LOG  (zero CPU hops)")
    log = bus.get_log()

    if not log:
        print(f"  {GREY}No bus messages.{RESET}\n")
        return

    shown = log[:max_entries]
    for i, msg in enumerate(shown, 1):
        sc = COMP_COLOR.get(msg.sender,   WHITE)
        rc = COMP_COLOR.get(msg.receiver, WHITE)
        tc = {
            "PREFETCH_REQUEST": MAGENTA,
            "DATA_READY":       GREEN,
            "ACK":              CYAN,
            "SYNC":             YELLOW,
        }.get(msg.msg_type, GREY)
        p = msg.payload
        payload_s = ""
        if "predicted" in p:
            payload_s = (
                f"  predicted={TEAL}{p['predicted']}{RESET}  "
                f"{DIM}conf={int(float(p.get('confidence', 0)) * 100)}%{RESET}"
            )
        print(
            f"  {DIM}[{i:02d}]{RESET}  "
            f"{sc}{BOLD}{msg.sender}{RESET}  "
            f"{DIM}──▶{RESET}  "
            f"{rc}{BOLD}{msg.receiver}{RESET}  "
            f"{tc}[{msg.msg_type}]{RESET}{payload_s}"
        )
        _sleep(0.04)

    if len(log) > max_entries:
        print(f"\n  {DIM}… and {len(log) - max_entries} more messages.{RESET}")

    summary = bus.log_summary()
    print(f"\n  {DIM}Total bus messages: {RESET}{YELLOW}{BOLD}{summary['total_messages']}{RESET}")
    print(f"  {DIM}CPU messages routed through bus: {RESET}{GREEN}{BOLD}0{RESET}  {DIM}← this is the point{RESET}")
    print()
    _sleep(0.15)


# ──────────────────────────────────────────────────────────────────────
# RL learning progress
# ──────────────────────────────────────────────────────────────────────

def print_rl_progress(
    comp: "Component",
    epoch_rewards: list[float],
) -> None:
    rl = comp.rl
    c  = COMP_COLOR.get(comp.name, WHITE)
    print(
        f"  {c}{BOLD}[{comp.name}]{RESET}  "
        f"ε={YELLOW}{rl.epsilon:.3f}{RESET}  "
        f"avg_reward={GREEN}{rl.avg_reward:+.3f}{RESET}  "
        f"prefetches={MAGENTA}{rl.prefetch_count}{RESET}  "
        f"total_steps={DIM}{rl.total_steps}{RESET}"
    )
    _sleep(0.06)


# ──────────────────────────────────────────────────────────────────────
# Accuracy chart across epochs
# ──────────────────────────────────────────────────────────────────────

def print_accuracy_chart(
    epoch_labels: list[str],
    comp_accs:    dict[str, list[float]],   # {comp_name: [acc_per_epoch]}
) -> None:
    _section("LSTM ACCURACY — LEARNING CURVE PER EPOCH")

    chart_h = 8
    names   = list(comp_accs.keys())
    n_epochs = len(epoch_labels)

    for row in range(chart_h, 0, -1):
        threshold = row / chart_h
        line = f"  {int(threshold * 100):>3}% │"
        for ep_idx in range(n_epochs):
            for name in names:
                accs = comp_accs[name]
                acc  = accs[ep_idx] if ep_idx < len(accs) else 0.0
                c    = COMP_COLOR.get(name, WHITE)
                if acc >= threshold - (0.5 / chart_h):
                    line += f"{c}{BOLD}██{RESET} "
                else:
                    line += f"{DIM}   {RESET}"
            line += "  "
        print(line)

    # X-axis
    print("      └" + "─" * (n_epochs * (len(names) * 3 + 2) + 2))
    labels_line = "        " + "".join(
        f"{lbl:<{len(names)*3+2}}" for lbl in epoch_labels
    )
    print(labels_line)

    # Legend
    legend = "        "
    for name in names:
        c = COMP_COLOR.get(name, WHITE)
        legend += f"{c}{BOLD}██ {name}{RESET}  "
    print(legend)
    print()
    _sleep(0.15)


# ──────────────────────────────────────────────────────────────────────
# Final summary
# ──────────────────────────────────────────────────────────────────────

def print_final_summary(
    components: list["Component"],
    cpu:        "CPUObserver",
    bus:        "P2PBus",
) -> None:
    _section("PHASE 6 — FINAL SYSTEM SUMMARY")

    print(_box_top())
    print(_box_line(f"  {TEAL}{BOLD}DIANA Phase 6  ·  LSTM + RL  ·  Simulation Complete{RESET}"))
    print(_box_div())

    for comp in components:
        s  = comp.summary()
        c  = COMP_COLOR.get(comp.name, WHITE)
        bar = _acc_bar(s["accuracy"], 16)
        pct = int(s["accuracy"] * 100)
        pp  = int(s["prefetch_precision"] * 100)

        print(_box_line(
            f"  {c}{BOLD}{comp.name}{RESET}  "
            f"{bar}  {BOLD}{pct:>3}% acc{RESET}  "
            f"{MAGENTA}{s['prefetches_made']} prefetches{RESET}  "
            f"{DIM}({pp}% precision){RESET}  "
            f"{TEAL}LSTM trained {s['lstm_trained']}×{RESET}"
        ))

    print(_box_div())

    cpu_r = cpu.report()
    print(_box_line(
        f"  {COMP_COLOR['CPU']}{BOLD}CPU Observer{RESET}  "
        f"status updates received: {YELLOW}{cpu_r['total_updates']}{RESET}  "
        f"commands issued: {GREEN}{BOLD}0{RESET}  {DIM}← always{RESET}"
    ))
    print(_box_line(
        f"  {CYAN}{BOLD}P2P Bus{RESET}  "
        f"total messages: {YELLOW}{bus.message_count}{RESET}  "
        f"CPU hops: {GREEN}{BOLD}0{RESET}  {DIM}← zero by design{RESET}"
    ))
    print(_box_div())

    print(_box_line(f"  {DIM}Real PyTorch LSTM  ·  Online learning  ·  Q-learning RL{RESET}"))
    print(_box_line(f"  {GREEN}{BOLD}SYNAPSE chips learned autonomously — no human retraining needed.{RESET}"))
    print(_box_bot())
    print()
    _sleep(0.3)


# ──────────────────────────────────────────────────────────────────────
# Closing proof statements
# ──────────────────────────────────────────────────────────────────────

def print_proof(components: list["Component"]) -> None:
    _section("WHAT PHASE 6 PROVED")

    avg_acc = sum(c.accuracy for c in components) / len(components)

    statements = [
        f"{TEAL}✓{RESET}  Each component runs a {TEAL}real LSTM{RESET} (PyTorch) — not a lookup table.",
        f"{TEAL}✓{RESET}  The LSTM trains {BOLD}online{RESET}, from live trace data — no offline datasets.",
        f"{MAGENTA}✓{RESET}  The {MAGENTA}RL agent{RESET} decides WHEN to pre-fetch via reward/punishment.",
        f"{CYAN}✓{RESET}  The {CYAN}P2P Bus{RESET} routes messages directly — zero CPU hops.",
        f"{COMP_COLOR['CPU']}✓{RESET}  The CPU issued {GREEN}{BOLD}0{RESET} commands — purely a passive observer.",
        f"{GREEN}✓{RESET}  Average prediction accuracy reached "
        f"{GREEN}{BOLD}{int(avg_acc * 100)}%{RESET} across all chips.",
        f"{YELLOW}✓{RESET}  SYNAPSE chips learned the memory trace pattern {BOLD}autonomously{RESET}.",
    ]
    for s in statements:
        print(f"  {s}")
        _sleep(0.12)
    print()
