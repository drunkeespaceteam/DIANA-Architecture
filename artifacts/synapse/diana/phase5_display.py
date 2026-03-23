"""
DIANA Phase 5 — Self-Healing display engine.

All terminal rendering for the healing simulation: banner, healing log
entries, per-round scorecards, before/after comparison, and the final
summary.  Uses the same ANSI colour vocabulary as Phases 1-4.
"""

from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synapse.healing import HealingChip, HealingEvent

from .display import BOLD, DIM, ITALIC, RESET

# ── Colour palette (consistent with viz_engine) ────────────────────────
CYAN    = "\033[38;5;51m"
GREEN   = "\033[38;5;82m"
YELLOW  = "\033[38;5;226m"
RED     = "\033[38;5;196m"
MAGENTA = "\033[38;5;201m"
ORANGE  = "\033[38;5;214m"
WHITE   = "\033[38;5;231m"
GREY    = "\033[38;5;244m"
PINK    = "\033[38;5;213m"

W = 64   # display width


# ──────────────────────────────────────────────────────────────────────
# Low-level helpers (mirror of viz_engine pattern)
# ──────────────────────────────────────────────────────────────────────

def _write(s: str) -> None:
    sys.stdout.write(s)
    sys.stdout.flush()


def _sleep(s: float) -> None:
    time.sleep(s)


def _pad(text: str, width: int) -> str:
    import re
    clean = re.sub(r"\033\[[0-9;]*m", "", text)
    pad = max(0, width - len(clean))
    return text + " " * pad


def _thin(w: int = W) -> str:
    return "  " + "─" * (w - 2)


def _thick(w: int = W) -> str:
    return "  " + "═" * (w - 2)


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


# ──────────────────────────────────────────────────────────────────────
# Phase 5 banner
# ──────────────────────────────────────────────────────────────────────

HEAL_BANNER = f"""
{BOLD}  ██████╗ ██╗ █████╗ ███╗   ██╗ █████╗     {PINK}Phase 5{RESET}
{BOLD}  ██╔══██╗██║██╔══██╗████╗  ██║██╔══██╗    {PINK}Self-Healing System{RESET}
{BOLD}  ██║  ██║██║███████║██╔██╗ ██║███████║    {PINK}Adaptive Intelligence{RESET}
{BOLD}  ██║  ██║██║██╔══██║██║╚██╗██║██╔══██║{RESET}
{BOLD}  ██████╔╝██║██║  ██║██║ ╚████║██║  ██║{RESET}
{BOLD}  ╚═════╝ ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝{RESET}
  {DIM}Detects wrong predictions · Heals itself · Never repeats mistakes{RESET}
"""


def print_heal_banner() -> None:
    print(HEAL_BANNER)


# ──────────────────────────────────────────────────────────────────────
# Pattern table — show what the chip currently believes
# ──────────────────────────────────────────────────────────────────────

def print_pattern_table(
    chip: "HealingChip",
    contexts: list[tuple[str, ...]],
    title: str = "LEARNED PATTERNS",
) -> None:
    _section(title)
    print(f"  {'CONTEXT':<22}  {'PREDICTED':<22}  {'CONF':>5}  {'STATUS'}")
    print(_thin())
    for ctx in contexts:
        pred = chip.predict_for_context(ctx)
        conf = chip.confidence_for_context(ctx)
        ctx_str  = f"{DIM}[{RESET}{ORANGE}{', '.join(ctx)}{RESET}{DIM}]{RESET}"
        if pred is None:
            pred_str   = f"{GREY}—{RESET}"
            conf_str   = f"{GREY}  n/a{RESET}"
            status_str = f"{GREY}no data{RESET}"
        else:
            pred_str = f"{CYAN}{BOLD}{pred}{RESET}"
            pct      = int(conf * 100)
            bar_len  = min(20, int(conf * 20))
            bar      = "█" * bar_len + "░" * (20 - bar_len)
            if conf >= 0.8:
                conf_str   = f"{GREEN}{BOLD}{pct:>3}%{RESET}"
                status_str = f"{GREEN}strong ✓{RESET}"
            elif conf >= 0.5:
                conf_str   = f"{YELLOW}{BOLD}{pct:>3}%{RESET}"
                status_str = f"{YELLOW}learning{RESET}"
            else:
                conf_str   = f"{RED}{BOLD}{pct:>3}%{RESET}"
                status_str = f"{RED}uncertain{RESET}"
        print(
            f"  {_pad(ctx_str, 32)}  {_pad(pred_str, 30)}  {conf_str}  {status_str}"
        )
        _sleep(0.06)
    print()


# ──────────────────────────────────────────────────────────────────────
# Single prediction step display
# ──────────────────────────────────────────────────────────────────────

def print_prediction_step(
    step_n:    int,
    context:   tuple[str, ...],
    predicted: str,
    actual:    str,
    conf:      float,
) -> None:
    ctx_str  = f"{ORANGE}{', '.join(context)}{RESET}"
    pct      = int(conf * 100)

    if predicted == actual:
        tick    = f"{GREEN}{BOLD}✓ CORRECT{RESET}"
        pred_c  = GREEN
        outcome = ""
    else:
        tick    = f"{RED}{BOLD}✗ WRONG{RESET}"
        pred_c  = RED
        outcome = f"  {DIM}actual: {RESET}{GREEN}{BOLD}{actual}{RESET}"

    print(
        f"  {DIM}[{step_n:02d}]{RESET}  "
        f"after {DIM}({RESET}{ctx_str}{DIM}){RESET}  →  "
        f"{pred_c}{BOLD}{predicted}{RESET}  "
        f"{DIM}({pct}% conf){RESET}  {tick}{outcome}"
    )
    _sleep(0.08)


# ──────────────────────────────────────────────────────────────────────
# Healing log entry — printed immediately after a wrong prediction
# ──────────────────────────────────────────────────────────────────────

def print_healing_event(event: "HealingEvent", delay: float = 0.05) -> None:
    if event.correct:
        print(
            f"    {DIM}└─ {RESET}"
            f"{GREEN}Pattern confidence increased!{RESET}  "
            f"{DIM}weight {event.old_weight:.3f} → {event.new_weight:.3f}{RESET}"
        )
        _sleep(delay)
        return

    # Wrong prediction — show full healing sequence
    print(f"    {DIM}└─ {RESET}{RED}{BOLD}Wrong prediction detected!{RESET}")
    _sleep(delay)

    pct_old = int(event.old_weight * 100)
    pct_new = int(event.new_weight * 100)
    bar_old = "█" * min(20, int(event.old_weight * 10))
    bar_new = "█" * min(20, int(event.new_weight * 10)) if event.new_weight > 0 else ""

    print(
        f"       {ORANGE}Pattern confidence reduced:{RESET}  "
        f"{DIM}[{bar_old:<20}] {pct_old}%{RESET}  {DIM}→{RESET}  "
        f"{DIM}[{RED}{bar_new:<20}{RESET}{DIM}] {pct_new}%{RESET}"
    )
    _sleep(delay)
    print(
        f"       {CYAN}Correct pattern reinforced:{RESET}  "
        f"{DIM}{event.predicted!r} penalised  ·  "
        f"{event.actual!r} boosted{RESET}"
    )
    _sleep(delay)
    if event.banished:
        print(
            f"       {MAGENTA}{BOLD}Pattern banished permanently!{RESET}  "
            f"{DIM}{event.predicted!r} will never be predicted in this context again{RESET}"
        )
        _sleep(delay)
    print(f"       {GREEN}{BOLD}Correction learned!{RESET}  "
          f"{DIM}This mistake will not happen again.{RESET}")
    _sleep(delay)


# ──────────────────────────────────────────────────────────────────────
# Round scorecard
# ──────────────────────────────────────────────────────────────────────

def _accuracy_bar(acc: float, width: int = 24) -> str:
    filled = int(acc * width)
    empty  = width - filled
    if acc >= 0.9:
        c = GREEN
    elif acc >= 0.5:
        c = YELLOW
    else:
        c = RED
    return f"{c}{'█' * filled}{RESET}{DIM}{'░' * empty}{RESET}"


def print_round_scorecard(
    round_n:    int,
    correct:    int,
    total:      int,
    wrong_log:  list["HealingEvent"],
) -> None:
    acc = correct / total if total else 0.0
    pct = int(acc * 100)
    bar = _accuracy_bar(acc)

    print()
    print(_box_top())
    print(_box_line(
        f"{BOLD}  ROUND {round_n} RESULT{RESET}  ·  "
        f"{correct}/{total} correct  {bar}  {BOLD}{pct}%{RESET}"
    ))
    if wrong_log:
        print(_box_div())
        for e in wrong_log:
            ctx_s = ", ".join(e.context)
            print(_box_line(
                f"  {RED}✗{RESET}  "
                f"{DIM}[{RESET}{ORANGE}{ctx_s}{RESET}{DIM}]{RESET}  "
                f"predicted {RED}{e.predicted}{RESET}  "
                f"{DIM}→ correct: {RESET}{GREEN}{e.actual}{RESET}"
            ))
    else:
        print(_box_div())
        print(_box_line(f"  {GREEN}{BOLD}No mistakes!  All predictions correct.{RESET}"))
    print(_box_bot())
    print()
    _sleep(0.2)


# ──────────────────────────────────────────────────────────────────────
# Before / After comparison
# ──────────────────────────────────────────────────────────────────────

def print_before_after(
    before_results: list[tuple[tuple, str, str, bool]],   # (ctx, predicted, actual, correct)
    after_results:  list[tuple[tuple, str, str, bool]],
) -> None:
    _section("BEFORE vs AFTER HEALING")

    before_correct = sum(1 for _, _, _, ok in before_results if ok)
    after_correct  = sum(1 for _, _, _, ok in after_results  if ok)
    total          = len(before_results)

    before_acc = before_correct / total if total else 0.0
    after_acc  = after_correct  / total if total else 0.0

    print(f"  {'CONTEXT':<24}  {'BEFORE':^20}  {'AFTER':^20}")
    print(_thin())

    for (ctx, bpred, bact, bok), (_, apred, aact, aok) in zip(before_results, after_results):
        ctx_s  = ", ".join(ctx)
        b_icon = f"{GREEN}✓{RESET}" if bok else f"{RED}✗{RESET}"
        a_icon = f"{GREEN}✓{RESET}" if aok else f"{RED}✗{RESET}"
        b_col  = GREEN if bok else RED
        a_col  = GREEN if aok else RED
        print(
            f"  {DIM}({RESET}{ORANGE}{ctx_s:<22}{RESET}{DIM}){RESET}  "
            f"{b_icon} {b_col}{bpred:<18}{RESET}  "
            f"{a_icon} {a_col}{apred:<18}{RESET}"
        )
        _sleep(0.07)

    print(_thin())
    b_bar = _accuracy_bar(before_acc, 16)
    a_bar = _accuracy_bar(after_acc, 16)

    print(
        f"\n  {'ACCURACY':<24}  "
        f"{b_bar} {RED}{BOLD}{int(before_acc*100):>3}%{RESET}    "
        f"{a_bar} {GREEN}{BOLD}{int(after_acc*100):>3}%{RESET}"
    )
    print()
    _sleep(0.2)


# ──────────────────────────────────────────────────────────────────────
# Healing progress chart (accuracy over rounds)
# ──────────────────────────────────────────────────────────────────────

def print_healing_progress(round_accuracies: list[float]) -> None:
    _section("HEALING PROGRESS — ACCURACY PER ROUND")

    chart_h = 8
    chart_w = max(len(round_accuracies) * 8, 40)

    # Draw chart
    for row in range(chart_h, 0, -1):
        threshold = row / chart_h
        line = f"  {int(threshold*100):>3}% │"
        for acc in round_accuracies:
            if acc >= threshold - (0.5 / chart_h):
                if acc >= 0.9:
                    line += f"  {GREEN}{BOLD}██{RESET}    "
                elif acc >= 0.5:
                    line += f"  {YELLOW}{BOLD}██{RESET}    "
                else:
                    line += f"  {RED}{BOLD}██{RESET}    "
            else:
                line += f"  {DIM}  {RESET}    "
        print(line)

    # X-axis
    axis = "      └" + "─" * (len(round_accuracies) * 8 + 2)
    print(axis)
    labels = "        " + "".join(f"Rnd {i+1:<3} " for i in range(len(round_accuracies)))
    print(labels)
    print()
    _sleep(0.15)


# ──────────────────────────────────────────────────────────────────────
# Final healing summary
# ──────────────────────────────────────────────────────────────────────

def print_healing_summary(
    chip: "HealingChip",
    total_rounds: int,
    final_round_correct: int = 0,
    final_round_total: int = 0,
) -> None:
    _section("SELF-HEALING SYSTEM — FINAL SUMMARY")

    mistakes       = chip.wrong_count
    banished       = len(chip.dead_patterns)
    overall_acc    = chip.accuracy
    overall_pct    = int(overall_acc * 100)
    overall_bar    = _accuracy_bar(overall_acc, 20)

    final_acc      = (final_round_correct / final_round_total) if final_round_total else 0.0
    final_pct      = int(final_acc * 100)
    final_bar      = _accuracy_bar(final_acc, 20)

    print(_box_top())
    print(_box_line(f"  {PINK}{BOLD}Phase 5  ·  Self-Healing Complete{RESET}"))
    print(_box_div())
    print(_box_line(
        f"  Total rounds simulated      : {YELLOW}{BOLD}{total_rounds}{RESET}"
    ))
    print(_box_line(
        f"  Total predictions made      : {YELLOW}{BOLD}{chip.total_predictions}{RESET}"
    ))
    print(_box_line(
        f"  Mistakes detected & healed  : {RED}{BOLD}{mistakes}{RESET}"
    ))
    print(_box_line(
        f"  Patterns permanently banned : {MAGENTA}{BOLD}{banished}{RESET}"
    ))
    print(_box_line(
        f"  Overall accuracy (all rnds) : {overall_bar}  {YELLOW}{BOLD}{overall_pct}%{RESET}"
    ))
    print(_box_line(
        f"  Final round accuracy        : {final_bar}  {GREEN}{BOLD}{final_pct}%{RESET}"
    ))
    print(_box_div())
    print(_box_line(
        f"  {DIM}Wrong predictions drop in confidence every round{RESET}"
    ))
    print(_box_line(
        f"  {DIM}Correct patterns grow stronger with each confirmation{RESET}"
    ))
    print(_box_line(
        f"  {DIM}Permanently banned patterns are excluded forever{RESET}"
    ))
    print(_box_line(
        f"  {GREEN}{BOLD}SYNAPSE healed itself with zero human intervention.{RESET}"
    ))
    print(_box_bot())
    print()
    _sleep(0.3)
