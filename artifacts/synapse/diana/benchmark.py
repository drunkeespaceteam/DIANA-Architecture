"""
DIANA Phase 3 — Benchmark entry point.

Runs all three tasks through both architectures and prints the full
comparison report.
"""

from __future__ import annotations

from .benchmark_tasks import ALL_TASKS
from .benchmark_engine import run_benchmark, TaskComparison
from .benchmark_display import (
    print_benchmark_header,
    print_task_comparison,
    print_overall_summary,
)


def run_benchmarks() -> None:
    print_benchmark_header()

    comparisons: list[TaskComparison] = []
    for task in ALL_TASKS:
        comp = run_benchmark(task)
        comparisons.append(comp)
        print_task_comparison(comp)

    print_overall_summary(comparisons)
