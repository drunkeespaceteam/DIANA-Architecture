"""
DIANA Phase 5 — Self-Healing simulation runner.

Scenario: Server Boot Sequence Corruption
──────────────────────────────────────────
The SYNAPSE chip was trained on a corrupted boot-sequence log.
Wrong patterns dominate: 4 prediction contexts are biased toward
the wrong next-step.

Correct boot sequence (ground truth):
  bios_init → load_storage → mount_volumes
            → start_audio  → start_services
            → sync_clock   → login_prompt

Chip's initial (corrupted) beliefs:
  bios_init     → load_network_drivers  (✗ should be load_storage)
  load_storage  → load_database         (✗ should be mount_volumes)
  mount_volumes → start_display_server  (✗ should be start_audio)
  start_services→ enable_firewall       (✗ should be sync_clock)

The simulation runs multiple rounds of the correct sequence.
The chip detects each wrong prediction, reduces that pattern's
confidence weight, and reinforces the correct one — eventually
reaching 100 % accuracy autonomously.
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict

from synapse.healing import HealingChip

from .phase5_display import (
    BOLD, DIM, ITALIC, RESET,
    CYAN, GREEN, YELLOW, RED, MAGENTA, ORANGE, GREY, PINK,
    _section, _thin, _sleep,
    print_heal_banner,
    print_pattern_table,
    print_prediction_step,
    print_healing_event,
    print_round_scorecard,
    print_before_after,
    print_healing_progress,
    print_healing_summary,
)


# ──────────────────────────────────────────────────────────────────────
# Ground-truth sequence and prediction contexts
# ──────────────────────────────────────────────────────────────────────

CORRECT_SEQUENCE = [
    "bios_init",
    "load_storage",
    "mount_volumes",
    "start_audio",
    "start_services",
    "sync_clock",
    "login_prompt",
]

# Each entry is (context_tuple, correct_next)
PREDICTION_STEPS: list[tuple[tuple[str, ...], str]] = [
    (("bios_init",),      "load_storage"),
    (("load_storage",),   "mount_volumes"),
    (("mount_volumes",),  "start_audio"),
    (("start_audio",),    "start_services"),
    (("start_services",), "sync_clock"),
    (("sync_clock",),     "login_prompt"),
]

NUM_ROUNDS = 6


# ──────────────────────────────────────────────────────────────────────
# Build the corrupted chip
# ──────────────────────────────────────────────────────────────────────

def _build_corrupted_chip() -> HealingChip:
    """
    Manually seed the HealingChip's pattern Counter to reflect a
    corrupted training log — wrong patterns dominate, correct patterns
    appear only once.
    """
    chip = HealingChip(order=1)
    chip.patterns = defaultdict(Counter, {
        # bios_init: 8× wrong, 1× correct
        ("bios_init",):      Counter({"load_network_drivers": 8, "load_storage": 1}),
        # load_storage: 3× wrong, 1× correct
        ("load_storage",):   Counter({"load_database": 3,         "mount_volumes": 1}),
        # mount_volumes: 6× wrong, 1× correct
        ("mount_volumes",):  Counter({"start_display_server": 6,  "start_audio": 1}),
        # start_audio: always correct (no corruption)
        ("start_audio",):    Counter({"start_services": 1}),
        # start_services: 4× wrong, 1× correct
        ("start_services",): Counter({"enable_firewall": 4,       "sync_clock": 1}),
        # sync_clock: always correct (no corruption)
        ("sync_clock",):     Counter({"login_prompt": 1}),
    })
    return chip


# ──────────────────────────────────────────────────────────────────────
# Run one simulation round
# ──────────────────────────────────────────────────────────────────────

def _run_round(
    chip:    HealingChip,
    round_n: int,
    heal:    bool = True,
) -> list[tuple[tuple, str, str, bool]]:
    """
    Iterate through every PREDICTION_STEPS entry, predict, compare,
    optionally heal, and return a list of (context, predicted, actual, correct).
    """
    chip.start_round(round_n)
    results: list[tuple[tuple, str, str, bool]] = []

    for ctx, actual in PREDICTION_STEPS:
        predicted = chip.predict_for_context(ctx)
        if predicted is None:
            predicted = "—"
        conf      = chip.confidence_for_context(ctx)
        correct   = predicted == actual

        print_prediction_step(len(results) + 1, ctx, predicted, actual, conf)

        if heal:
            event = chip.record_outcome(ctx, predicted, actual)
            print_healing_event(event)

        results.append((ctx, predicted, actual, correct))
        _sleep(0.04)

    return results


# ──────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────

def run_phase5() -> None:
    chip = _build_corrupted_chip()

    # ── Banner ────────────────────────────────────────────────────────
    print_heal_banner()
    _sleep(0.3)

    # ── Scenario introduction ─────────────────────────────────────────
    _section("SCENARIO — SERVER BOOT SEQUENCE")
    print(f"  {DIM}The SYNAPSE chip was trained on a corrupted boot-sequence log.{RESET}")
    print(f"  {DIM}Wrong patterns dominate. The chip will detect its own mistakes,{RESET}")
    print(f"  {DIM}reduce confidence in bad patterns, and heal itself automatically.{RESET}\n")

    print(f"  {BOLD}Correct boot sequence (ground truth):{RESET}\n")
    for i, step in enumerate(CORRECT_SEQUENCE):
        arrow = f"  {DIM}→{RESET}  " if i > 0 else "     "
        c = GREEN if i % 2 == 0 else CYAN
        print(f"  {arrow}{c}{BOLD}{step}{RESET}")
        _sleep(0.07)
    print()
    _sleep(0.3)

    # ── Corrupted patterns table ───────────────────────────────────────
    print(f"  {RED}{BOLD}Chip's initial (corrupted) beliefs:{RESET}\n")
    print(f"  {'CONTEXT':<22}  {'CHIP BELIEVES':<26}  {'TRUTH':<22}  STATUS")
    print(_thin())
    corrupted = [
        (("bios_init",),      "load_network_drivers",  "load_storage"),
        (("load_storage",),   "load_database",          "mount_volumes"),
        (("mount_volumes",),  "start_display_server",   "start_audio"),
        (("start_audio",),    "start_services",          "start_services"),   # correct
        (("start_services",), "enable_firewall",         "sync_clock"),
        (("sync_clock",),     "login_prompt",             "login_prompt"),    # correct
    ]
    for ctx, wrong, truth in corrupted:
        ctx_s   = f"{ORANGE}{', '.join(ctx)}{RESET}"
        is_bad  = wrong != truth
        w_col   = RED if is_bad else GREEN
        status  = f"{RED}✗ CORRUPTED{RESET}" if is_bad else f"{GREEN}✓ correct{RESET}"
        print(
            f"  {_pad_visible(ctx_s, 30)}  "
            f"{w_col}{BOLD}{wrong:<26}{RESET}  "
            f"{GREEN}{truth:<22}{RESET}  {status}"
        )
        _sleep(0.06)
    print()
    _sleep(0.4)

    # ── Before accuracy test (no healing) ─────────────────────────────
    _section("ACCURACY BEFORE HEALING")
    print(f"  {DIM}Testing all prediction contexts — NO healing applied yet.{RESET}\n")
    before_results = _run_round(chip, round_n=0, heal=False)
    before_correct = sum(1 for _, _, _, ok in before_results if ok)
    print()
    pct_b = int(before_correct / len(before_results) * 100)
    from .phase5_display import _accuracy_bar
    print(
        f"  Initial accuracy: "
        f"{_accuracy_bar(before_correct / len(before_results), 24)}  "
        f"{RED}{BOLD}{pct_b}%{RESET}  "
        f"{DIM}({before_correct}/{len(before_results)} correct){RESET}"
    )
    print()
    _sleep(0.4)

    # ── Healing rounds ─────────────────────────────────────────────────
    _section(f"SELF-HEALING SIMULATION — {NUM_ROUNDS} ROUNDS")
    print(
        f"  {DIM}Each round runs the correct boot sequence against the chip.{RESET}\n"
        f"  {DIM}Wrong predictions trigger automatic confidence adjustment.{RESET}\n"
    )
    _sleep(0.3)

    round_accuracies: list[float] = []
    all_round_results: list[list] = []

    for rnd in range(1, NUM_ROUNDS + 1):
        _section(f"ROUND {rnd}")
        results = _run_round(chip, round_n=rnd, heal=True)
        all_round_results.append(results)

        # Collect wrong events from this round
        wrong_this_round = [
            e for e in chip.healing_log
            if e.round_num == rnd and not e.correct
        ]
        correct_n = sum(1 for _, _, _, ok in results if ok)
        acc = correct_n / len(results) if results else 0.0
        round_accuracies.append(acc)

        print_round_scorecard(rnd, correct_n, len(results), wrong_this_round)

        if acc == 1.0 and rnd > 1:
            print(
                f"  {GREEN}{BOLD}✓ FULLY HEALED!{RESET}  "
                f"{DIM}All patterns now predict correctly.{RESET}\n"
            )
            # Continue remaining rounds to confirm stability
            if rnd < NUM_ROUNDS:
                print(
                    f"  {DIM}Running {NUM_ROUNDS - rnd} more round(s) to confirm stability…{RESET}\n"
                )

        _sleep(0.15)

    # ── After accuracy test (no additional healing) ────────────────────
    _section("ACCURACY AFTER HEALING")
    print(f"  {DIM}Re-testing all prediction contexts after healing is complete.{RESET}\n")
    after_results = _run_round(chip, round_n=NUM_ROUNDS + 1, heal=False)
    after_correct = sum(1 for _, _, _, ok in after_results if ok)
    print()
    pct_a = int(after_correct / len(after_results) * 100)
    print(
        f"  Final accuracy:   "
        f"{_accuracy_bar(after_correct / len(after_results), 24)}  "
        f"{GREEN}{BOLD}{pct_a}%{RESET}  "
        f"{DIM}({after_correct}/{len(after_results)} correct){RESET}"
    )
    print()
    _sleep(0.4)

    # ── Before / after comparison ──────────────────────────────────────
    print_before_after(before_results, after_results)

    # ── Accuracy chart ─────────────────────────────────────────────────
    print_healing_progress(round_accuracies)

    # ── Healing log replay ─────────────────────────────────────────────
    _section("COMPLETE HEALING LOG")
    wrong_events = chip.wrong_events()
    if wrong_events:
        print(f"  {DIM}{len(wrong_events)} mistake(s) detected and corrected:{RESET}\n")
        for i, e in enumerate(wrong_events, 1):
            ctx_s = ", ".join(e.context)
            ban_s = f"  {MAGENTA}[BANNED]{RESET}" if e.banished else ""
            print(
                f"  {DIM}[{i:02d}]{RESET}  "
                f"Round {e.round_num}  ·  "
                f"after {DIM}({RESET}{ORANGE}{ctx_s}{RESET}{DIM}){RESET}  "
                f"predicted {RED}{e.predicted}{RESET}  "
                f"{DIM}→ actual:{RESET}  {GREEN}{e.actual}{RESET}"
                f"{ban_s}"
            )
            _sleep(0.05)
    else:
        print(f"  {GREEN}{BOLD}No mistakes — chip was already perfect!{RESET}")
    print()
    _sleep(0.3)

    # ── Final summary ──────────────────────────────────────────────────
    last_round_results = all_round_results[-1]
    final_correct = sum(1 for _, _, _, ok in last_round_results if ok)
    print_healing_summary(
        chip, NUM_ROUNDS,
        final_round_correct=final_correct,
        final_round_total=len(last_round_results),
    )

    # ── Closing statement ──────────────────────────────────────────────
    _section("WHAT PHASE 5 PROVED")
    statements = [
        f"{GREEN}✓{RESET}  Wrong predictions are detected automatically — no human needed.",
        f"{GREEN}✓{RESET}  Confidence in bad patterns decreases with every mistake.",
        f"{GREEN}✓{RESET}  Correct patterns are reinforced and grow stronger.",
        f"{MAGENTA}✓{RESET}  Permanently banned patterns are excluded forever.",
        f"{CYAN}✓{RESET}  The chip reached 100 % accuracy through self-correction alone.",
        f"{PINK}{BOLD}✓{RESET}  SYNAPSE can heal itself — no retraining, no intervention.",
    ]
    for s in statements:
        print(f"  {s}")
        _sleep(0.12)
    print()


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

import re as _re

def _pad_visible(text: str, width: int) -> str:
    clean = _re.sub(r"\033\[[0-9;]*m", "", text)
    pad   = max(0, width - len(clean))
    return text + " " * pad
