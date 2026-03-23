"""
DIANA Architecture — SYNAPSE Chip Simulation
CLI entry point.

Usage:
  python main.py --demo        Phase 1: built-in learning demo
  python main.py               Phase 1: interactive REPL
  python main.py --diana       Phase 2: P2P multi-chip simulation
  python main.py --benchmark   Phase 3: Traditional vs DIANA benchmark
  python main.py --visualize   Phase 4: real-time network visualization
  python main.py --heal        Phase 5: self-healing system simulation
  python main.py --lstm        Phase 6: LSTM + RL SynapseBrain simulation

  python main.py --tasks "A,B,A,B,A"    train on comma-separated tasks
  python main.py --file tasks.txt        train from file (one task per line)
  python main.py --order 3               set n-gram context window (default 2)
"""

from __future__ import annotations

import argparse
import sys

from synapse.core import SynapseChip
from synapse.display import (
    print_divider,
    print_header,
    print_prediction,
    print_summary,
)
from synapse.repl import run_repl


DEMO_SEQUENCES = [
    ["wake_up", "brush_teeth", "shower", "breakfast", "commute", "work"],
    ["wake_up", "brush_teeth", "shower", "breakfast", "commute", "work"],
    ["wake_up", "brush_teeth", "shower", "breakfast", "commute", "work"],
    ["wake_up", "gym", "shower", "breakfast", "commute", "work"],
    ["wake_up", "brush_teeth", "shower", "breakfast", "commute"],
]


def run_demo() -> None:
    chip = SynapseChip(order=2)
    print_header()
    print("  DEMO MODE — Training on a daily routine sequence\n")

    all_tasks = [t for seq in DEMO_SEQUENCES for t in seq]
    chip.train(all_tasks)

    print_summary(chip.summary())
    print()

    test_cases = [
        ["wake_up", "brush_teeth"],
        ["wake_up", "gym"],
        ["shower", "breakfast"],
        ["breakfast", "commute"],
    ]

    print("  Prediction Tests")
    print_divider()
    for history in test_cases:
        prediction = chip.predict(history)
        confidence = chip.confidence(history)
        top_k = chip.predict_top_k(k=3, history=history)
        print_prediction(prediction, confidence, top_k, history)
        print()


def run_from_task_list(tasks: list[str], order: int) -> None:
    chip = SynapseChip(order=order)
    print_header()

    print(f"  Training on {len(tasks)} tasks ...\n")
    chip.train(tasks)
    print_summary(chip.summary())
    print()

    prediction = chip.predict()
    confidence = chip.confidence()
    top_k = chip.predict_top_k(k=3)

    print("  Prediction after full sequence")
    print_divider()
    print_prediction(prediction, confidence, top_k, chip.task_log)
    print()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="synapse",
        description="SYNAPSE — Intelligent task prediction chip",
    )
    parser.add_argument(
        "--tasks",
        type=str,
        default=None,
        help="Comma-separated task sequence to train on, e.g. 'A,B,A,B,A'",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to a text file with one task per line",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the built-in demo sequence",
    )
    parser.add_argument(
        "--diana",
        action="store_true",
        help="Run the DIANA Phase 2 P2P architecture simulation",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run the DIANA Phase 3 benchmark: Traditional vs DIANA architecture",
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Run the DIANA Phase 4 real-time network visualization dashboard",
    )
    parser.add_argument(
        "--heal",
        action="store_true",
        help="Run the DIANA Phase 5 self-healing system simulation",
    )
    parser.add_argument(
        "--lstm",
        action="store_true",
        help="Run the DIANA Phase 6 LSTM + RL SynapseBrain simulation",
    )
    parser.add_argument(
        "--order",
        type=int,
        default=2,
        help="N-gram order (context window size). Default: 2",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    if args.lstm:
        from diana.phase6_runner import run_phase6
        run_phase6()
        return

    if args.heal:
        from diana.phase5_runner import run_phase5
        run_phase5()
        return

    if args.visualize:
        from diana.visualizer import run_visualizer
        run_visualizer()
        return

    if args.benchmark:
        from diana.benchmark import run_benchmarks
        run_benchmarks()
        return

    if args.diana:
        from diana.scenario import run_diana_scenario
        run_diana_scenario()
        return

    if args.demo:
        run_demo()
        return

    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                tasks = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"Error: file '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
        run_from_task_list(tasks, order=args.order)
        return

    if args.tasks:
        tasks = [t.strip() for t in args.tasks.split(",") if t.strip()]
        run_from_task_list(tasks, order=args.order)
        return

    run_repl(order=args.order)


if __name__ == "__main__":
    main()
