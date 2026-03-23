"""
DIANA Phase 4 — Visualization rendering engine.

All terminal drawing primitives: component boxes, network graph,
animated message flows, activity feed, and the final communication map.
Works in any ANSI-capable terminal (including mobile).
"""

from __future__ import annotations

import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .display import BOLD, DIM, ITALIC, RESET, COLOR


# ── Extra colours ─────────────────────────────────────────────────────
CYAN    = "\033[38;5;51m"
MAGENTA = "\033[38;5;201m"
WHITE   = "\033[38;5;231m"
GREY    = "\033[38;5;244m"
GREEN   = "\033[38;5;82m"
YELLOW  = "\033[38;5;226m"
RED     = "\033[38;5;196m"
BG_DARK = "\033[48;5;235m"

# ── Status colours ────────────────────────────────────────────────────
STATUS_COLOR = {
    "IDLE":        GREY,
    "ACTIVE":      GREEN,
    "PREDICTING":  YELLOW,
    "SENDING":     "\033[38;5;214m",   # amber
    "RECEIVING":   CYAN,
    "COMPLETE":    "\033[38;5;34m",    # dark green
}

STATUS_ICON = {
    "IDLE":        "○",
    "ACTIVE":      "◉",
    "PREDICTING":  "◈",
    "SENDING":     "▶",
    "RECEIVING":   "◀",
    "COMPLETE":    "✓",
}

MSG_TYPE_COLOR = {
    "alert":   "\033[38;5;214m",
    "ready":   GREEN,
    "preload": CYAN,
    "status":  "\033[38;5;197m",
    "observe": GREY,
}

MSG_TYPE_LABEL = {
    "alert":   "ALERT  ",
    "ready":   "READY  ",
    "preload": "PRELOAD",
    "status":  "STATUS ",
    "observe": "OBS    ",
}

W = 64   # display width


# ──────────────────────────────────────────────────────────────────────
# Low-level helpers
# ──────────────────────────────────────────────────────────────────────

def _write(s: str) -> None:
    sys.stdout.write(s)
    sys.stdout.flush()


def _sleep(s: float) -> None:
    time.sleep(s)


def _pad(text: str, width: int, align: str = "left") -> str:
    """Pad text to `width` visible characters (strips ANSI for measurement)."""
    import re
    clean = re.sub(r"\033\[[0-9;]*m", "", text)
    pad = max(0, width - len(clean))
    if align == "center":
        lpad = pad // 2
        return " " * lpad + text + " " * (pad - lpad)
    if align == "right":
        return " " * pad + text
    return text + " " * pad


def _box_line(content: str, width: int = W) -> str:
    """Return a full-width box line: ║ content (padded) ║"""
    return f"  ║ {_pad(content, width - 6)} ║"


def _hline(char: str = "═", width: int = W) -> str:
    return "  ╠" + char * (width - 4) + "╣"


def _top(width: int = W) -> str:
    return "  ╔" + "═" * (width - 4) + "╗"


def _bot(width: int = W) -> str:
    return "  ╚" + "═" * (width - 4) + "╝"


def _thin_line(width: int = W) -> str:
    return "  " + "─" * (width - 2)


# ──────────────────────────────────────────────────────────────────────
# Phase 4 header banner
# ──────────────────────────────────────────────────────────────────────

VIZ_BANNER = f"""
{BOLD}  ██████╗ ██╗ █████╗ ███╗   ██╗ █████╗     {CYAN}Phase 4{RESET}
{BOLD}  ██╔══██╗██║██╔══██╗████╗  ██║██╔══██╗    {CYAN}Network Visualization{RESET}
{BOLD}  ██║  ██║██║███████║██╔██╗ ██║███████║    {CYAN}Dashboard{RESET}
{BOLD}  ██║  ██║██║██╔══██║██║╚██╗██║██╔══██║{RESET}
{BOLD}  ██████╔╝██║██║  ██║██║ ╚████║██║  ██║{RESET}
{BOLD}  ╚═════╝ ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝{RESET}
  {DIM}Real-Time P2P Component Visualization{RESET}
"""


def print_viz_banner() -> None:
    print(VIZ_BANNER)


# ──────────────────────────────────────────────────────────────────────
# CPU status box
# ──────────────────────────────────────────────────────────────────────

def print_cpu_box(msgs_received: int, commands_sent: int = 0) -> None:
    cpu_c  = COLOR["CPU"]
    proof  = f"{GREEN}NONE — NEVER COMMANDS{RESET}" if commands_sent == 0 else f"{RED}{commands_sent}{RESET}"
    print(_top())
    print(_box_line(f"{cpu_c}{BOLD}  CPU REPORTER  ·  PASSIVE OBSERVER{RESET}"))
    print(_hline("─"))
    print(_box_line(
        f"  Status reports received : {YELLOW}{BOLD}{msgs_received}{RESET}"
        f"    Commands issued : {proof}"
    ))
    print(_box_line(
        f"  {DIM}CPU is informed, never in control. It cannot send commands.{RESET}"
    ))
    print(_bot())
    print()


# ──────────────────────────────────────────────────────────────────────
# Network graph
# ──────────────────────────────────────────────────────────────────────

def _comp_box(name: str, status: str, active_msg: str = "") -> list[str]:
    """Return a 3-line component box as a list of strings (no newlines)."""
    c  = COLOR.get(name, WHITE)
    sc = STATUS_COLOR.get(status, GREY)
    ic = STATUS_ICON.get(status, "○")
    top    = f"┌─────────────┐"
    mid    = f"│ {c}{BOLD}{name:<4}{RESET}  {sc}{ic} {status:<9}{RESET}│"
    if active_msg:
        bot = f"│ {DIM}{active_msg[:13]:<13}{RESET} │"
    else:
        bot = f"└─────────────┘"
    close  = f"└─────────────┘"
    return [top, mid, bot if not active_msg else bot, close if active_msg else ""]


def print_network_graph(states: dict[str, str], cpu_msgs: int,
                        active_flows: list[tuple[str, str]] | None = None) -> None:
    """
    Print a full network graph:
    - CPU passive observer box at top
    - Triangle mesh: SSD ── GPU (top row), RAM (bottom centre)
    - Active connection lines turn amber when a flow is active

    All lines are designed with known visible widths so ANSI codes
    don't affect horizontal alignment.
    """
    if active_flows is None:
        active_flows = []
    flow_set = {(s, r) for s, r in active_flows}

    def is_active(a: str, b: str) -> bool:
        return (a, b) in flow_set or (b, a) in flow_set

    # Per-component coloured labels (known visible sizes)
    def comp_label(name: str) -> str:
        return f"{COLOR.get(name, WHITE)}{BOLD}{name}{RESET}"

    def stat_label(status: str) -> str:
        ic = STATUS_ICON.get(status, "○")
        sc = STATUS_COLOR.get(status, GREY)
        return f"{sc}{ic} {status:<9}{RESET}"   # 11 visible chars

    ssd_s = states.get("SSD", "IDLE")
    gpu_s = states.get("GPU", "IDLE")
    ram_s = states.get("RAM", "IDLE")

    # Box inner content – each is: "NNN  s SSSSSSSSS" (visible: 3+2+11 = 16 chars)
    ssd_inner = f"{comp_label('SSD')}  {stat_label(ssd_s)}"
    gpu_inner = f"{comp_label('GPU')}  {stat_label(gpu_s)}"
    ram_inner = f"{comp_label('RAM')}  {stat_label(ram_s)}"

    # Horizontal SSD↔GPU connection (14 visible chars)
    if is_active("SSD", "GPU"):
        h_conn = f"{YELLOW}{BOLD}══════════════{RESET}"
        lr_arr = f"{YELLOW}{BOLD}◀═══════════════▶{RESET}"
    else:
        h_conn = f"{DIM}──────────────{RESET}"
        lr_arr = f"{DIM}◀───────────────▶{RESET}"

    # Diagonal legs: SSD↘ and GPU↙
    sl = f"{YELLOW}{BOLD}╲{RESET}" if is_active("SSD", "RAM") else f"{DIM}╲{RESET}"
    sr = f"{YELLOW}{BOLD}╱{RESET}" if is_active("GPU", "RAM") else f"{DIM}╱{RESET}"

    cpu_c = COLOR.get("CPU", WHITE)
    n_str = f"{YELLOW}{BOLD}{cpu_msgs}{RESET}" if cpu_msgs else f"{GREY}0{RESET}"

    G = "  "   # left margin
    print()
    print(f"{G}  ╔═══════════════════════════════════════════════════════╗")
    print(f"{G}  ║  {BOLD}DIANA P2P NETWORK  ·  LIVE{RESET}                           ║")
    print(f"{G}  ╠═══════════════════════════════════════════════════════╣")
    print(f"{G}  ║                                                       ║")
    # CPU inner box
    print(f"{G}  ║    ┌──────────────────────────────────────────────┐   ║")
    print(f"{G}  ║    │  {cpu_c}{BOLD}CPU REPORTER{RESET}  ●  PASSIVE OBSERVER           │   ║")
    print(f"{G}  ║    │  status msgs: {n_str}   commands: {GREEN}NONE — NEVER{RESET}      │   ║")
    print(f"{G}  ║    └──────────────────────┬───────────────────────┘   ║")
    print(f"{G}  ║                           {DIM}│ ↑ status reports, read-only{RESET} ║")
    print(f"{G}  ║    {DIM}──────────────────────┼──────────────────────{RESET}         ║")
    print(f"{G}  ║                                                       ║")
    # SSD box  (left col: chars 4–23)  |  connection  |  GPU box (right col)
    print(f"{G}  ║  ┌────────────────────┐  {h_conn}  ┌────────────────────┐  ║")
    print(f"{G}  ║  │ {ssd_inner} │  {lr_arr}  │ {gpu_inner} │  ║")
    print(f"{G}  ║  └──────────┬─────────┘                  └─────────┬──────────┘  ║")
    # Diagonal lines toward RAM
    print(f"{G}  ║             │     {sl}                        {sr}     │             ║")
    print(f"{G}  ║             │        {sl}                    {sr}        │             ║")
    print(f"{G}  ║             └─────────{sl}                  {sr}─────────┘             ║")
    # RAM box (centred)
    print(f"{G}  ║                        ┌────────────────────┐                    ║")
    print(f"{G}  ║                        │ {ram_inner} │                    ║")
    print(f"{G}  ║                        └────────────────────┘                    ║")
    print(f"{G}  ║                                                       ║")
    print(f"{G}  ╚═══════════════════════════════════════════════════════╝")
    print()


# ──────────────────────────────────────────────────────────────────────
# Animated message flow
# ──────────────────────────────────────────────────────────────────────

def animate_message(
    sender: str,
    receiver: str,
    content: str,
    msg_type: str,
    speed: float = 0.03,
) -> None:
    sc = COLOR.get(sender,   WHITE)
    rc = COLOR.get(receiver, WHITE)
    tc = MSG_TYPE_COLOR.get(msg_type, WHITE)
    tl = MSG_TYPE_LABEL.get(msg_type, msg_type.upper())

    label_w  = 30
    bar_w    = 28
    content_trunc = f'"{content[:40]}"'

    print(
        f"\n  {sc}{BOLD}{sender:<3}{RESET} "
        f"{DIM}══[{RESET}{tc}{tl}{RESET}{DIM}]══▶{RESET} "
        f"{rc}{BOLD}{receiver}{RESET}  "
        f"{DIM}{content_trunc}{RESET}"
    )

    # Transmission progress bar (animated in-place with \r)
    _write(f"  {'':5}")
    for i in range(bar_w + 1):
        filled  = "▓" * i
        empty   = "░" * (bar_w - i)
        pct     = int(i / bar_w * 100)
        _write(f"\r  {DIM}transmitting  [{RESET}{tc}{filled}{RESET}{DIM}{empty}] {pct:>3}%{RESET}")
        _sleep(speed)

    _write(f"\r  {GREEN}{BOLD}delivered      [{'▓' * bar_w}] SENT ✓{RESET}          \n\n")
    _sleep(0.15)


# ──────────────────────────────────────────────────────────────────────
# State change announcement
# ──────────────────────────────────────────────────────────────────────

def print_state_change(component: str, new_state: str, reason: str = "") -> None:
    c  = COLOR.get(component, WHITE)
    sc = STATUS_COLOR.get(new_state, GREY)
    ic = STATUS_ICON.get(new_state, "○")
    print(
        f"  {c}{BOLD}[{component}]{RESET} "
        f"→ {sc}{BOLD}{ic} {new_state}{RESET}"
        + (f"  {DIM}{reason}{RESET}" if reason else "")
    )
    time.sleep(0.12)


# ──────────────────────────────────────────────────────────────────────
# Live activity feed entry
# ──────────────────────────────────────────────────────────────────────

def print_activity_entry(
    n: int,
    sender: str,
    receiver: str,
    content: str,
    msg_type: str,
    reasoning: str = "",
) -> None:
    sc  = COLOR.get(sender,   WHITE)
    rc  = COLOR.get(receiver, WHITE)
    tc  = MSG_TYPE_COLOR.get(msg_type, WHITE)
    tl  = MSG_TYPE_LABEL.get(msg_type, msg_type.upper())
    num = f"{DIM}[{n:02d}]{RESET}"
    print(
        f"  {num}  {sc}{BOLD}{sender:<3}{RESET} "
        f"{DIM}──▶{RESET} "
        f"{rc}{BOLD}{receiver:<3}{RESET}  "
        f"{tc}[{tl.strip()}]{RESET}  "
        f"{DIM}{content[:38]}{RESET}"
    )
    if reasoning:
        print(f"  {'':8}{DIM}↳ {reasoning}{RESET}")


# ──────────────────────────────────────────────────────────────────────
# Section divider
# ──────────────────────────────────────────────────────────────────────

def print_section(title: str) -> None:
    pad = max(0, W - 6 - len(title)) // 2
    line = "─" * pad + f" {BOLD}{title}{RESET} " + "─" * pad
    print(f"\n  {line}\n")


def print_thinking(component: str, text: str) -> None:
    c = COLOR.get(component, WHITE)
    print(f"  {c}{BOLD}{component}{RESET} {DIM}◈ thinking:{RESET}  {ITALIC}{text}{RESET}")
    time.sleep(0.1)


# ──────────────────────────────────────────────────────────────────────
# Final network communication map
# ──────────────────────────────────────────────────────────────────────

def print_communication_map(comm_log: list[dict]) -> None:
    from collections import Counter

    # Tally directional pairs
    pair_count: dict[tuple, int] = Counter()
    type_count: dict[str, int]   = Counter()
    comp_sent:  dict[str, int]   = Counter()
    comp_recv:  dict[str, int]   = Counter()

    for entry in comm_log:
        s, r, t = entry["sender"], entry["receiver"], entry["type"]
        if t != "observe":
            pair_count[(s, r)] += 1
            type_count[t]      += 1
            comp_sent[s]       += 1
            comp_recv[r]       += 1

    all_nodes = sorted({n for pair in pair_count for n in pair})

    print_section("FULL NETWORK COMMUNICATION MAP")

    # Matrix header
    row_nodes = [n for n in ["SSD", "GPU", "RAM", "CPU"] if n in all_nodes or n == "CPU"]
    col_nodes = [n for n in ["SSD", "GPU", "RAM", "CPU"] if n in all_nodes or n == "CPU"]

    header = f"  {'FROM ╲ TO':<10}" + "".join(f"{COLOR.get(n,'')}{BOLD}{n:<10}{RESET}" for n in col_nodes)
    print(header)
    print(_thin_line())

    for frm in ["SSD", "GPU", "RAM"]:
        c = COLOR.get(frm, WHITE)
        row = f"  {c}{BOLD}{frm:<10}{RESET}"
        for to in col_nodes:
            cnt = pair_count.get((frm, to), 0)
            if cnt:
                bar = "█" * cnt
                row += f"{YELLOW}{cnt} msg{'s' if cnt>1 else ''} {bar:<6}{RESET}"
            else:
                row += f"{DIM}  ─     {RESET}  "
        print(row)

    print(_thin_line())

    # Per-component totals
    print(f"\n  {BOLD}Per-component activity{RESET}\n")
    for comp in ["SSD", "GPU", "RAM", "CPU"]:
        c = COLOR.get(comp, WHITE)
        sent = comp_sent.get(comp, 0)
        recv = comp_recv.get(comp, 0)
        bar_s = "▓" * sent
        bar_r = "░" * recv
        note = ""
        if comp == "CPU":
            note = f"  {GREEN}← received only, never sent{RESET}"
        print(
            f"  {c}{BOLD}{comp:<6}{RESET}  "
            f"sent: {YELLOW}{BOLD}{sent:>2}{RESET} {DIM}{bar_s:<8}{RESET}  "
            f"received: {CYAN}{BOLD}{recv:>2}{RESET} {DIM}{bar_r:<8}{RESET}"
            f"{note}"
        )

    # Message type breakdown
    print(f"\n  {BOLD}Message type breakdown{RESET}\n")
    for mtype, cnt in sorted(type_count.items(), key=lambda x: -x[1]):
        tc  = MSG_TYPE_COLOR.get(mtype, WHITE)
        tl  = MSG_TYPE_LABEL.get(mtype, mtype)
        bar = "█" * (cnt * 4)
        print(f"  {tc}[{tl.strip():<7}]{RESET}  {cnt} message{'s' if cnt>1 else ''}  {DIM}{bar}{RESET}")

    total = sum(type_count.values())
    print(f"\n  {DIM}Total P2P messages exchanged: {RESET}{YELLOW}{BOLD}{total}{RESET}")
    print(f"  {DIM}CPU commands issued:          {RESET}{GREEN}{BOLD}0{RESET}  {DIM}← this is the point{RESET}")
    print()
    print(_thin_line())
    print(f"\n  {DIM}All activity above was autonomous. "
          f"No component asked the CPU for permission.{RESET}\n")
