"""
SYNAPSE — Intelligent Chip Pattern Recognition Core

Learns task sequences using n-gram (Markov chain) pattern analysis and
predicts the most likely next task given recent history.
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from typing import Optional


class SynapseChip:
    """
    Simulates an intelligent chip that watches tasks, learns patterns,
    and predicts the next task using n-gram frequency analysis.

    Attributes:
        order:    The n-gram order (how many past tasks are used as context).
        patterns: Mapping from context tuple -> Counter of following tasks.
        task_log: Full ordered history of observed tasks.
    """

    def __init__(self, order: int = 2) -> None:
        if order < 1:
            raise ValueError("order must be at least 1")
        self.order: int = order
        self.patterns: dict[tuple[str, ...], Counter] = defaultdict(Counter)
        self.task_log: list[str] = []

    # ------------------------------------------------------------------
    # Learning
    # ------------------------------------------------------------------

    def observe(self, task: str) -> None:
        """Record a single observed task and update learned patterns."""
        task = task.strip()
        if not task:
            raise ValueError("Task name must not be empty.")

        self.task_log.append(task)

        for n in range(1, self.order + 1):
            if len(self.task_log) >= n + 1:
                context = tuple(self.task_log[-(n + 1) : -1])
                following = self.task_log[-1]
                self.patterns[context][following] += 1

    def train(self, tasks: list[str]) -> None:
        """Ingest a sequence of tasks and learn from all of them."""
        for task in tasks:
            self.observe(task)

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, history: Optional[list[str]] = None) -> Optional[str]:
        """
        Predict the next task based on the provided or stored history.

        Strategy: try from highest to lowest order context until a match
        is found, then return the most frequently observed follower.

        Returns None if no prediction can be made.
        """
        if history is None:
            history = self.task_log

        if not history:
            return None

        for n in range(min(self.order, len(history)), 0, -1):
            context = tuple(history[-n:])
            if context in self.patterns and self.patterns[context]:
                return self.patterns[context].most_common(1)[0][0]

        return None

    def predict_top_k(
        self, k: int = 3, history: Optional[list[str]] = None
    ) -> list[tuple[str, int]]:
        """
        Return the top-k predicted next tasks with their observation counts.

        Returns an empty list if no prediction can be made.
        """
        if history is None:
            history = self.task_log

        if not history:
            return []

        for n in range(min(self.order, len(history)), 0, -1):
            context = tuple(history[-n:])
            if context in self.patterns and self.patterns[context]:
                return self.patterns[context].most_common(k)

        return []

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    def confidence(self, history: Optional[list[str]] = None) -> float:
        """
        Return a 0–1 confidence score for the top prediction.

        Calculated as the proportion of times the top prediction was seen
        after the current context, relative to all observed followers.
        """
        if history is None:
            history = self.task_log

        if not history:
            return 0.0

        for n in range(min(self.order, len(history)), 0, -1):
            context = tuple(history[-n:])
            if context in self.patterns and self.patterns[context]:
                counter = self.patterns[context]
                top_count = counter.most_common(1)[0][1]
                total = sum(counter.values())
                return round(top_count / total, 4)

        return 0.0

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        """Return a human-readable summary of what SYNAPSE has learned."""
        unique_tasks = sorted(set(self.task_log))
        pattern_count = sum(len(v) for v in self.patterns.values())
        return {
            "order": self.order,
            "tasks_observed": len(self.task_log),
            "unique_tasks": unique_tasks,
            "pattern_count": pattern_count,
            "context_count": len(self.patterns),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Serialize the chip state to a JSON file."""
        state = {
            "order": self.order,
            "task_log": self.task_log,
            "patterns": {
                json.dumps(list(k)): dict(v)
                for k, v in self.patterns.items()
            },
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    @classmethod
    def load(cls, path: str) -> "SynapseChip":
        """Deserialize a chip state from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        chip = cls(order=state["order"])
        chip.task_log = state["task_log"]
        chip.patterns = defaultdict(Counter, {
            tuple(json.loads(k)): Counter(v)
            for k, v in state["patterns"].items()
        })
        return chip

    def reset(self) -> None:
        """Clear all learned patterns and history."""
        self.patterns.clear()
        self.task_log.clear()
