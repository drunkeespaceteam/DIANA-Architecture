"""
SYNAPSE display helpers — formatted console output.
"""

from __future__ import annotations

from typing import Optional


HEADER = r"""
  ███████╗██╗   ██╗███╗   ██╗ █████╗ ██████╗ ███████╗███████╗
  ██╔════╝╚██╗ ██╔╝████╗  ██║██╔══██╗██╔══██╗██╔════╝██╔════╝
  ███████╗ ╚████╔╝ ██╔██╗ ██║███████║██████╔╝███████╗█████╗  
  ╚════██║  ╚██╔╝  ██║╚██╗██║██╔══██║██╔═══╝ ╚════██║██╔══╝  
  ███████║   ██║   ██║ ╚████║██║  ██║██║     ███████║███████╗
  ╚══════╝   ╚═╝   ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝     ╚══════╝╚══════╝
  DIANA Architecture — SYNAPSE Chip Simulation
"""

DIVIDER = "  " + "─" * 58


def print_header() -> None:
    print(HEADER)


def print_divider() -> None:
    print(DIVIDER)


def print_prediction(
    prediction: Optional[str],
    confidence: float,
    top_k: list[tuple[str, int]],
    history: list[str],
) -> None:
    context_str = " → ".join(history[-3:]) if history else "(none)"
    print(f"\n  Context  : {context_str}")

    if prediction is None:
        print("  Prediction: ⚠  Not enough data yet — keep adding tasks.")
        return

    bar_len = int(confidence * 20)
    bar = "█" * bar_len + "░" * (20 - bar_len)
    pct = int(confidence * 100)

    print(f"  Prediction: ✦  {prediction}")
    print(f"  Confidence: [{bar}] {pct}%")

    if len(top_k) > 1:
        print("  Alternatives:")
        for task, count in top_k[1:]:
            alt_conf = count / sum(c for _, c in top_k)
            alt_pct = int(alt_conf * 100)
            print(f"    • {task}  ({alt_pct}%)")


def print_summary(summary: dict) -> None:
    print_divider()
    print("  SYNAPSE Memory Snapshot")
    print_divider()
    print(f"  N-gram order     : {summary['order']}")
    print(f"  Tasks observed   : {summary['tasks_observed']}")
    print(f"  Unique tasks     : {len(summary['unique_tasks'])}")
    print(f"  Patterns learned : {summary['pattern_count']}")
    print(f"  Known tasks      : {', '.join(summary['unique_tasks']) or '—'}")
    print_divider()
