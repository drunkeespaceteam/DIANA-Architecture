"""
CPU Reporter — passive status receiver in the DIANA Architecture.

The CPU never issues commands or controls any component.
It only receives status notifications and logs them.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class StatusEntry:
    timestamp: float
    source: str
    status: str


class CPUReporter:
    """
    Passive CPU Reporter. Components can notify it of status updates.
    It records everything but never sends instructions back.
    """

    def __init__(self) -> None:
        self.log: list[StatusEntry] = []

    def notify(self, source: str, status: str) -> None:
        """Receive a status update from a component. Never replies."""
        self.log.append(StatusEntry(
            timestamp=time.time(),
            source=source,
            status=status,
        ))

    def print_report(self, indent: str = "  ") -> None:
        from .display import COLOR, RESET, BOLD
        print(f"\n{indent}{BOLD}CPU STATUS LOG  ({len(self.log)} entries){RESET}")
        print(f"{indent}" + "─" * 54)
        for i, entry in enumerate(self.log, 1):
            src_color = COLOR.get(entry.source, "")
            print(
                f"{indent}  [{i:02d}]  "
                f"{src_color}{entry.source:<6}{RESET}  →  {entry.status}"
            )
        print(f"{indent}" + "─" * 54)
