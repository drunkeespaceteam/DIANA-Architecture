"""
DIANA Architecture — display constants and helpers.
"""

from __future__ import annotations

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
ITALIC = "\033[3m"

# Per-component colours
COLOR = {
    "SSD": "\033[38;5;214m",   # amber
    "GPU": "\033[38;5;82m",    # green
    "RAM": "\033[38;5;39m",    # blue
    "CPU": "\033[38;5;197m",   # pink/red
}

ARROW  = f"{DIM}──▶{RESET}"
DOTTED = f"{DIM}···{RESET}"

DIANA_HEADER = f"""
{BOLD}  ██████╗ ██╗ █████╗ ███╗   ██╗ █████╗ {RESET}
{BOLD}  ██╔══██╗██║██╔══██╗████╗  ██║██╔══██╗{RESET}
{BOLD}  ██║  ██║██║███████║██╔██╗ ██║███████║{RESET}
{BOLD}  ██║  ██║██║██╔══██║██║╚██╗██║██╔══██║{RESET}
{BOLD}  ██████╔╝██║██║  ██║██║ ╚████║██║  ██║{RESET}
{BOLD}  ╚═════╝ ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝{RESET}
  {DIM}Distributed Intelligence Architecture for Networked Autonomy{RESET}
  Phase 2  ·  Peer-to-Peer Component Intelligence
"""

DIVIDER = "  " + "─" * 58


def chip_label(name: str) -> str:
    c = COLOR.get(name, "")
    return f"{c}{BOLD}[{name}]{RESET}"


def print_diana_header() -> None:
    print(DIANA_HEADER)


def print_divider(title: str = "") -> None:
    if title:
        pad = (56 - len(title)) // 2
        print(f"  {'─' * pad} {BOLD}{title}{RESET} {'─' * pad}")
    else:
        print(DIVIDER)


def print_message(
    sender: str,
    receiver: str,
    content: str,
    msg_type: str,
    reasoning: str | None = None,
) -> None:
    sc = COLOR.get(sender, "")
    rc = COLOR.get(receiver, "")
    type_tag = {
        "alert":   f"\033[38;5;214m[ALERT]{RESET}",
        "ready":   f"\033[38;5;82m[READY]{RESET}",
        "preload": f"\033[38;5;39m[PRELOAD]{RESET}",
        "observe": f"{DIM}[OBS]{RESET}",
        "status":  f"\033[38;5;197m[STATUS]{RESET}",
    }.get(msg_type, f"[{msg_type.upper()}]")

    sender_str   = f"{sc}{BOLD}{sender:<4}{RESET}"
    receiver_str = f"{rc}{BOLD}{receiver:<4}{RESET}"
    print(f"  {sender_str} {ARROW} {receiver_str}  {type_tag}  {content}")
    if reasoning:
        print(f"  {' ' * 12}{DIM}↳ reasoning: {reasoning}{RESET}")


def print_chip_thought(name: str, thought: str) -> None:
    c = COLOR.get(name, "")
    print(f"  {c}{BOLD}{name}{RESET} {DIM}thinks:{RESET} {ITALIC}{thought}{RESET}")
