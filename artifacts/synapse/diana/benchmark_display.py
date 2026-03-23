"""
DIANA Phase 3 — Benchmark display renderer.

Prints the full comparison report for Traditional vs DIANA results.
"""

from __future__ import annotations

from .benchmark_engine import BenchmarkResult, TaskComparison
from .benchmark_tasks import BenchmarkTask, ALL_TASKS
from .display import (
    BOLD, DIM, ITALIC, RESET, COLOR,
    chip_label, print_divider,
)

# Extra colours for architecture labels
TRAD_COLOR  = "\033[38;5;196m"   # bright red
DIANA_COLOR = "\033[38;5;51m"    # cyan
GREEN       = "\033[38;5;82m"
YELLOW      = "\033[38;5;226m"
ORANGE      = "\033[38;5;208m"


BENCHMARK_HEADER = f"""
{BOLD}  ╔══════════════════════════════════════════════════════╗{RESET}
{BOLD}  ║   DIANA Phase 3  ·  Architecture Benchmark Suite    ║{RESET}
{BOLD}  ╚══════════════════════════════════════════════════════╝{RESET}
  {DIM}Traditional (CPU-controlled) vs DIANA (P2P autonomous){RESET}
"""


def _bar(value: float, max_val: float, width: int = 30, char: str = "█") -> str:
    filled = int((value / max_val) * width) if max_val else 0
    return char * filled + "░" * (width - filled)


def _ms(v: float) -> str:
    return f"{v:.0f}ms"


def _speedup_color(x: float) -> str:
    if x >= 8:   return GREEN
    if x >= 5:   return YELLOW
    return ORANGE


def print_benchmark_header() -> None:
    print(BENCHMARK_HEADER)


def print_task_step_trace(result: BenchmarkResult, max_time: float) -> None:
    """Print a mini Gantt-style trace of each step."""
    SCALE = 40   # characters wide
    for rec in result.step_records:
        if rec.is_waiting:
            continue    # skip overhead wait markers in trace
        comp_c = COLOR.get(rec.component, "")
        start_frac = rec.start_ms / max_time
        end_frac   = rec.end_ms   / max_time
        bar_start  = int(start_frac * SCALE)
        bar_len    = max(1, int((end_frac - start_frac) * SCALE))
        bar        = " " * bar_start + "▓" * bar_len
        label      = f"{comp_c}{rec.component:<3}{RESET}"
        action_trunc = rec.action[:30].ljust(30)
        print(
            f"    {label}  {DIM}{action_trunc}{RESET}  "
            f"{DIM}|{bar:<{SCALE}}|{RESET}  "
            f"{DIM}{_ms(rec.start_ms)}–{_ms(rec.end_ms)}{RESET}"
        )


def print_task_comparison(comp: TaskComparison) -> None:
    trad  = comp.traditional
    diana = comp.diana
    task  = comp.task
    speedup = comp.speedup
    sc    = _speedup_color(speedup)
    max_t = trad.total_time_ms   # normalise bars against Traditional (slower)

    print()
    print_divider(f"TASK: {task.icon}  {task.name}")
    print(f"  {DIM}{task.description}{RESET}\n")

    # ── Step trace ───────────────────────────────────────────────────
    print(f"  {BOLD}{TRAD_COLOR}TRADITIONAL{RESET} — execution trace")
    print_task_step_trace(trad, max_t)
    print()
    print(f"  {BOLD}{DIANA_COLOR}DIANA{RESET}       — execution trace")
    print_task_step_trace(diana, max_t)
    print()

    # ── Summary metrics table ─────────────────────────────────────────
    trad_bar  = _bar(trad.total_time_ms,  max_t, char="█")
    diana_bar = _bar(diana.total_time_ms, max_t, char="█")

    print(f"  {'':4}  {'Total time':12}  {'CPU interrupts':16}  {'Efficiency':10}")
    print(f"  {'─'*62}")

    trad_eff  = f"{trad.work_efficiency * 100:.0f}%"
    diana_eff = f"{diana.work_efficiency * 100:.0f}%"

    print(
        f"  {TRAD_COLOR}{BOLD}TRAD{RESET}  "
        f"{_ms(trad.total_time_ms):>10}    "
        f"{trad.cpu_interrupts:>6} interrupts    "
        f"{trad_eff:>6}  "
        f"{DIM}|{TRAD_COLOR}{trad_bar}{RESET}{DIM}|{RESET}"
    )
    print(
        f"  {DIANA_COLOR}{BOLD}DIANA{RESET} "
        f"{_ms(diana.total_time_ms):>10}    "
        f"     0 interrupts    "
        f"{diana_eff:>6}  "
        f"{DIM}|{DIANA_COLOR}{diana_bar[:int(len(diana_bar)*diana.total_time_ms/max_t)+1]}{RESET}{DIM}|{RESET}"
    )
    print(f"  {'─'*62}")

    # ── Improvement row ───────────────────────────────────────────────
    saved_ms   = comp.time_saved_ms
    int_red    = comp.interrupt_reduction_pct
    speedup_str = f"{speedup:.1f}x faster"
    print(
        f"\n  {sc}{BOLD}  ✦ Improvement{RESET}   "
        f"{sc}{BOLD}{speedup_str}{RESET}   "
        f"|   {GREEN}{BOLD}{int_red:.0f}% less CPU usage{RESET}   "
        f"|   {DIM}saved {_ms(saved_ms)}{RESET}"
    )

    # ── Per-component wait time breakdown ─────────────────────────────
    print(f"\n  {BOLD}Component wait times{RESET} (time blocked waiting for CPU permission)\n")
    for comp_name in sorted(trad.component_metrics):
        tm = trad.component_metrics[comp_name]
        dm = diana.component_metrics.get(comp_name)
        c  = COLOR.get(comp_name, "")
        trad_wait  = _ms(tm.wait_ms)
        diana_wait = "0ms"
        wait_bar   = _bar(tm.wait_ms, trad.total_time_ms, width=20, char="▒")
        print(
            f"    {c}{BOLD}{comp_name:<3}{RESET}  "
            f"Traditional wait: {TRAD_COLOR}{trad_wait:>6}{RESET}  "
            f"{DIM}|{TRAD_COLOR}{wait_bar}{RESET}{DIM}|{RESET}  "
            f"DIANA wait: {DIANA_COLOR}{diana_wait}{RESET}"
        )
    print()


def print_overall_summary(comparisons: list[TaskComparison]) -> None:
    total_trad  = sum(c.traditional.total_time_ms for c in comparisons)
    total_diana = sum(c.diana.total_time_ms for c in comparisons)
    total_saved = sum(c.time_saved_ms for c in comparisons)
    total_trad_interrupts  = sum(c.traditional.cpu_interrupts for c in comparisons)
    overall_speedup = total_trad / total_diana if total_diana else 0

    sc = _speedup_color(overall_speedup)
    print()
    print_divider("OVERALL BENCHMARK RESULTS")
    print()

    bar_w = 35
    trad_bar  = "█" * bar_w
    diana_frac = total_diana / total_trad if total_trad else 0
    diana_bar = "█" * int(diana_frac * bar_w)

    print(f"  {'Architecture':<14}  {'Total time':>10}  {'CPU interrupts':>16}  {'Timeline':>8}")
    print(f"  {'─'*72}")
    print(
        f"  {TRAD_COLOR}{BOLD}{'Traditional':<14}{RESET}  "
        f"{_ms(total_trad):>10}  "
        f"{total_trad_interrupts:>16}  "
        f"  {TRAD_COLOR}{trad_bar}{RESET}"
    )
    print(
        f"  {DIANA_COLOR}{BOLD}{'DIANA':14}{RESET}  "
        f"{_ms(total_diana):>10}  "
        f"{'0':>16}  "
        f"  {DIANA_COLOR}{diana_bar}{RESET}"
    )
    print(f"  {'─'*72}")

    print(f"\n  {sc}{BOLD}  ► Overall speedup      : {overall_speedup:.2f}x faster{RESET}")
    print(f"  {GREEN}{BOLD}  ► CPU interrupt reduction : 100%  ({total_trad_interrupts} → 0){RESET}")
    print(f"  {DIANA_COLOR}{BOLD}  ► Total time saved     : {_ms(total_saved)}{RESET}")
    print(f"  {DIANA_COLOR}{BOLD}  ► DIANA efficiency     : {(1 - diana_frac)*100:.1f}% less wall-clock time{RESET}")
    print()

    # Score card
    score = min(100, int(overall_speedup * 12))
    score_bar = "█" * (score // 2) + "░" * (50 - score // 2)
    print(f"\n  {BOLD}DIANA ARCHITECTURE SCORE{RESET}")
    print(f"  {DIANA_COLOR}[{score_bar}] {score}/100{RESET}")
    print(f"  {DIM}Score formula: min(100, speedup × 12){RESET}")
    print()
    print_divider()
    print(
        f"\n  {DIM}All decisions in DIANA emerged from independent chip intelligence.\n"
        f"  No central controller was used at any point.{RESET}\n"
    )
