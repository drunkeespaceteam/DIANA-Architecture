"""
SYNAPSE Phase 6 — RLAgent: Reinforcement Learning pre-fetch decision engine.

Uses tabular Q-learning with epsilon-greedy exploration to decide when a
SYNAPSE chip should speculatively pre-fetch the predicted next address.

Actions:
    WAIT (0)     — serve the request on demand; conserve bandwidth.
    PREFETCH (1) — proactively load the predicted address now.

Rewards:
    PREFETCH + correct prediction  : +1.0   (latency saved!)
    PREFETCH + wrong prediction    : -0.5   (bandwidth wasted, eviction cost)
    WAIT     + correct prediction  : +0.1   (served, but no latency benefit)
    WAIT     + wrong prediction    :  0.0   (miss was unavoidable)

State space: (confidence_bucket × hit_streak)
    conf_bucket ∈ {0,1,2,3,4}  — LSTM confidence binned into 5 equal intervals
    hit_streak  ∈ {0,1,2,3+}  — recent consecutive correct predictions (capped)
"""

from __future__ import annotations

import random
from collections import defaultdict

WAIT     = 0
PREFETCH = 1

REWARD: dict[tuple[int, bool], float] = {
    (PREFETCH, True):  +1.0,
    (PREFETCH, False): -0.5,
    (WAIT,     True):  +0.1,
    (WAIT,     False):  0.0,
}

ACTION_NAME = {WAIT: "WAIT", PREFETCH: "PREFETCH"}


def _conf_bucket(conf: float) -> int:
    """Map a 0–1 confidence score to one of 5 discrete buckets."""
    return min(4, int(conf * 5))


class RLAgent:
    """
    Tabular Q-learning agent for the SYNAPSE pre-fetch decision.

    State  : (conf_bucket, hit_streak)
    Actions: WAIT (0)  or  PREFETCH (1)
    Policy : epsilon-greedy with exponential decay
    """

    def __init__(
        self,
        alpha:         float = 0.25,    # learning rate
        gamma:         float = 0.90,    # discount factor
        epsilon:       float = 0.50,    # initial exploration rate
        epsilon_decay: float = 0.97,    # per-step decay multiplier
        epsilon_min:   float = 0.05,    # minimum exploration rate
        seed:          int   = 42,
    ) -> None:
        self.alpha         = alpha
        self.gamma         = gamma
        self.epsilon       = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min   = epsilon_min
        random.seed(seed)

        # Q[state] = [Q(WAIT), Q(PREFETCH)]
        self.Q: dict[tuple[int, int], list[float]] = defaultdict(lambda: [0.0, 0.0])

        self._hit_streak   = 0
        self.total_steps   = 0
        self.prefetch_count = 0
        self.reward_total  = 0.0

        # Deferred update: we store (state, action) from choose_action
        # and update Q once the outcome is known.
        self._last_state:  tuple[int, int] | None = None
        self._last_action: int | None             = None

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def _state(self, conf: float) -> tuple[int, int]:
        return (_conf_bucket(conf), min(3, self._hit_streak))

    # ------------------------------------------------------------------
    # Action selection
    # ------------------------------------------------------------------

    def choose_action(self, conf: float) -> int:
        """
        Epsilon-greedy action selection.
        Stores (state, action) for the deferred Q-update.
        """
        state = self._state(conf)
        self._last_state = state

        if random.random() < self.epsilon:
            action = random.choice([WAIT, PREFETCH])
        else:
            q = self.Q[state]
            action = PREFETCH if q[PREFETCH] >= q[WAIT] else WAIT

        self._last_action = action
        if action == PREFETCH:
            self.prefetch_count += 1
        return action

    @property
    def last_action_name(self) -> str:
        return ACTION_NAME.get(self._last_action, "—")

    # ------------------------------------------------------------------
    # Q-learning update
    # ------------------------------------------------------------------

    def learn(self, hit: bool, next_conf: float) -> float:
        """
        Update Q-table based on the outcome of the last chosen action.

        Args:
            hit:       True if the last prediction was correct.
            next_conf: LSTM confidence for the upcoming prediction
                       (used to compute the next-state value).

        Returns:
            Reward received for the last action.
        """
        if self._last_state is None or self._last_action is None:
            return 0.0

        action = self._last_action
        reward = REWARD[(action, hit)]

        # Update hit-streak
        self._hit_streak = min(3, self._hit_streak + 1) if hit else 0

        # Q-learning Bellman update
        next_state = self._state(next_conf)
        best_next  = max(self.Q[next_state])
        old_q      = self.Q[self._last_state][action]
        new_q      = old_q + self.alpha * (
            reward + self.gamma * best_next - old_q
        )
        self.Q[self._last_state][action] = new_q

        # Decay exploration
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

        self.total_steps   += 1
        self.reward_total  += reward
        return reward

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def avg_reward(self) -> float:
        return self.reward_total / max(1, self.total_steps)

    def summary(self) -> dict:
        return {
            "epsilon":       round(self.epsilon, 4),
            "total_steps":   self.total_steps,
            "prefetch_count": self.prefetch_count,
            "avg_reward":    round(self.avg_reward, 4),
        }
