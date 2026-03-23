"""
SYNAPSE interactive REPL — feeds tasks one by one and shows live predictions.
"""

from __future__ import annotations

from .core import SynapseChip
from .display import print_divider, print_header, print_prediction, print_summary

HELP_TEXT = """
  Commands:
    <task name>   — record a task and get a prediction
    predict       — show current prediction without recording a task
    summary       — display learned patterns summary
    reset         — clear all memory
    help          — show this message
    quit / exit   — exit SYNAPSE
"""


def run_repl(order: int = 2, seed: list[str] | None = None) -> None:
    """Start the interactive SYNAPSE REPL."""
    chip = SynapseChip(order=order)
    print_header()
    print(f"  Order: {order}-gram  |  Type 'help' for commands.\n")

    if seed:
        chip.train(seed)
        print(f"  Loaded {len(seed)} seed tasks: {' → '.join(seed)}\n")

    while True:
        try:
            raw = input("  synapse> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Shutting down SYNAPSE. Goodbye.")
            break

        if not raw:
            continue

        cmd = raw.lower()

        if cmd in ("quit", "exit"):
            print("  Shutting down SYNAPSE. Goodbye.")
            break

        elif cmd == "help":
            print(HELP_TEXT)

        elif cmd == "summary":
            print_summary(chip.summary())

        elif cmd == "reset":
            chip.reset()
            print("  Memory cleared.")

        elif cmd == "predict":
            prediction = chip.predict()
            confidence = chip.confidence()
            top_k = chip.predict_top_k(k=3)
            print_prediction(prediction, confidence, top_k, chip.task_log)
            print()

        else:
            chip.observe(raw)
            prediction = chip.predict()
            confidence = chip.confidence()
            top_k = chip.predict_top_k(k=3)
            print_prediction(prediction, confidence, top_k, chip.task_log)
            print()
