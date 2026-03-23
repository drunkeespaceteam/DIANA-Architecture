"""
SYNAPSE Phase 5 — Self-Healing Chip

Extends SynapseChip with a self-healing layer that:
  - Tracks per-pattern confidence weights (separate from raw counts)
  - Penalises wrong predictions (weight × PENALTY_MULT)
  - Reinforces correct predictions (weight × REINFORCE_MULT)
  - Permanently bans patterns whose weight drops below DEAD_THRESHOLD
  - Maintains a structured HealingLog for display
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from synapse.core import SynapseChip


# ── Tuning knobs ───────────────────────────────────────────────────────
PENALTY_MULT    = 0.40   # weight multiplier on a wrong prediction
REINFORCE_MULT  = 1.50   # weight multiplier on a correct prediction
REINFORCE_CAP   = 4.00   # maximum weight (prevents runaway reinforcement)
DEAD_THRESHOLD  = 0.04   # weight below this → pattern permanently banned


@dataclass
class HealingEvent:
    """Structured record of a single prediction outcome."""
    round_num:    int
    context:      tuple[str, ...]
    predicted:    str
    actual:       str
    correct:      bool
    old_weight:   float
    new_weight:   float
    banished:     bool = False         # wrong pattern dropped below DEAD_THRESHOLD
    reinforced:   bool = False         # correct pattern weight increased


class HealingChip(SynapseChip):
    """
    A SynapseChip with an adaptive confidence-weight layer.

    On top of the raw n-gram counts learned by SynapseChip, each
    (context, candidate) pair carries a floating-point weight that
    starts at 1.0.  The effective score used during prediction is:

        score(candidate) = raw_count × weight

    Predictions are ranked by effective score, not raw count.
    Permanently banned patterns are excluded from consideration.
    """

    def __init__(self, order: int = 1) -> None:
        super().__init__(order=order)
        self.weights:       dict[tuple, float] = {}    # (context, task) → weight
        self.dead_patterns: set[tuple]         = set() # (context, task) permanently banned
        self.healing_log:   list[HealingEvent] = []
        self.total_predictions = 0
        self.correct_count     = 0
        self.wrong_count       = 0
        self._current_round    = 0

    # ------------------------------------------------------------------
    # Weighted prediction (overrides SynapseChip.predict)
    # ------------------------------------------------------------------

    def _effective_scores(self, context: tuple[str, ...]) -> dict[str, float]:
        """Return effective scores for all live candidates given a context."""
        if context not in self.patterns or not self.patterns[context]:
            return {}
        scores: dict[str, float] = {}
        for task, count in self.patterns[context].items():
            key = (context, task)
            if key in self.dead_patterns:
                continue
            w = self.weights.get(key, 1.0)
            scores[task] = count * w
        return scores

    def predict(self, history: Optional[list[str]] = None) -> Optional[str]:
        if history is None:
            history = self.task_log
        if not history:
            return None

        for n in range(min(self.order, len(history)), 0, -1):
            context = tuple(history[-n:])
            scores = self._effective_scores(context)
            if scores:
                return max(scores, key=scores.get)

        return None

    def predict_for_context(self, context: tuple[str, ...]) -> Optional[str]:
        """Predict directly from an explicit context tuple."""
        scores = self._effective_scores(context)
        return max(scores, key=scores.get) if scores else None

    def confidence_for_context(self, context: tuple[str, ...]) -> float:
        """Return a 0-1 confidence score using weighted effective scores."""
        scores = self._effective_scores(context)
        if not scores:
            return 0.0
        total = sum(scores.values())
        top   = max(scores.values())
        return round(top / total, 4) if total else 0.0

    # ------------------------------------------------------------------
    # Healing: record outcome and update weights
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        context:   tuple[str, ...],
        predicted: str,
        actual:    str,
    ) -> HealingEvent:
        """
        Compare the predicted task to the actual task that occurred.
        Update weights accordingly and append a HealingEvent to the log.
        """
        self.total_predictions += 1
        key_pred   = (context, predicted)
        key_actual = (context, actual)

        old_w = self.weights.get(key_pred, 1.0)

        if predicted == actual:
            # ── Correct ────────────────────────────────────────────────
            self.correct_count += 1
            new_w = min(REINFORCE_CAP, old_w * REINFORCE_MULT)
            self.weights[key_pred] = new_w
            event = HealingEvent(
                round_num  = self._current_round,
                context    = context,
                predicted  = predicted,
                actual     = actual,
                correct    = True,
                old_weight = old_w,
                new_weight = new_w,
                reinforced = True,
            )
        else:
            # ── Wrong — heal ───────────────────────────────────────────
            self.wrong_count += 1
            new_w = old_w * PENALTY_MULT
            self.weights[key_pred] = new_w

            banished = False
            if new_w < DEAD_THRESHOLD:
                self.dead_patterns.add(key_pred)
                banished = True

            # Reinforce the correct pattern (even if count was 0 we need an entry)
            correct_old = self.weights.get(key_actual, 1.0)
            correct_new = min(REINFORCE_CAP, correct_old * REINFORCE_MULT)
            self.weights[key_actual] = correct_new

            event = HealingEvent(
                round_num  = self._current_round,
                context    = context,
                predicted  = predicted,
                actual     = actual,
                correct    = False,
                old_weight = old_w,
                new_weight = new_w,
                banished   = banished,
                reinforced = True,
            )

        self.healing_log.append(event)
        return event

    # ------------------------------------------------------------------
    # Round tracking
    # ------------------------------------------------------------------

    def start_round(self, n: int) -> None:
        self._current_round = n

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def accuracy(self) -> float:
        if self.total_predictions == 0:
            return 0.0
        return round(self.correct_count / self.total_predictions, 4)

    @property
    def corrections_made(self) -> int:
        return self.wrong_count

    def wrong_events(self) -> list[HealingEvent]:
        return [e for e in self.healing_log if not e.correct]

    def correct_events(self) -> list[HealingEvent]:
        return [e for e in self.healing_log if e.correct]
