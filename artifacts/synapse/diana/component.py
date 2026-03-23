"""
DIANA Phase 6 — Component and CPUObserver.

Component: autonomous hardware node with its own SynapseBrain (LSTM) and
           RLAgent (pre-fetch policy) connected via the P2P Bus.

CPUObserver: purely passive — receives one-way "Task Complete" status
             notifications.  It cannot send commands or influence any
             component's behaviour.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from synapse.brain import SynapseBrain
from synapse.rl_agent import RLAgent, PREFETCH

if TYPE_CHECKING:
    from .p2p_bus import P2PBus, BusMessage


# ──────────────────────────────────────────────────────────────────────
# CPU Observer — passive, read-only
# ──────────────────────────────────────────────────────────────────────

class CPUObserver:
    """
    The CPU in the DIANA architecture.

    Design contract:
      - Receives "Task Complete" status pushes from Components.
      - CANNOT send commands, route messages, or influence behaviour.
      - Commands issued: always 0.
    """

    def __init__(self) -> None:
        self.status_log:     list[dict] = []
        self.commands_issued = 0         # enforced to remain 0

    def receive_status(
        self,
        sender:   str,
        status:   str,
        metadata: dict | None = None,
    ) -> None:
        """Accept a one-way status notification.  No response, no command."""
        self.status_log.append({
            "sender": sender,
            "status": status,
            "meta":   metadata or {},
        })

    def report(self) -> dict:
        return {
            "total_updates":   len(self.status_log),
            "senders":         sorted({e["sender"] for e in self.status_log}),
            "commands_issued": 0,   # always 0 — this is the point
        }


# ──────────────────────────────────────────────────────────────────────
# Step record (one observed event's full outcome)
# ──────────────────────────────────────────────────────────────────────

class StepRecord:
    """Structured snapshot of one component step for display."""
    __slots__ = (
        "step_n", "component", "event",
        "pred", "conf", "action",
        "hit", "reward", "loss",
    )

    def __init__(self) -> None:
        self.step_n:    int        = 0
        self.component: str        = ""
        self.event:     str        = ""
        self.pred:      str | None = None
        self.conf:      float      = 0.0
        self.action:    str        = "WAIT"
        self.hit:       bool | None = None
        self.reward:    float      = 0.0
        self.loss:      float | None = None


# ──────────────────────────────────────────────────────────────────────
# Component — the core autonomous hardware node
# ──────────────────────────────────────────────────────────────────────

class Component:
    """
    Autonomous hardware component in the DIANA P2P network.

    Each Component owns:
      - A SynapseBrain (LSTM) trained online from live memory traces.
      - An RLAgent (Q-learning) that decides when to pre-fetch.
      - A P2PBus reference for direct peer-to-peer messaging.
      - A CPUObserver reference for one-way status push (never commands).

    The observe() loop:
      1. Resolve the previous pending prediction (hit / miss) → RL update.
      2. Train the LSTM on the (context → current event) pair.
      3. Append the event to rolling history.
      4. Predict the next event → ask RL whether to pre-fetch.
      5. If PREFETCH: broadcast PREFETCH_REQUEST to all peers via P2P Bus.
      6. Push "event_processed" status to CPU Observer.
    """

    def __init__(
        self,
        name:      str,
        vocab:     list[str],
        bus:       "P2PBus",
        cpu:       CPUObserver,
        embed_dim: int = 8,
        hidden:    int = 16,
        window:    int = 4,
    ) -> None:
        self.name   = name
        self.vocab  = vocab
        self.bus    = bus
        self.cpu    = cpu
        self._window = window

        self.brain = SynapseBrain(
            vocab, embed_dim=embed_dim, hidden=hidden, window=window
        )
        self.rl = RLAgent()

        self._history: list[str] = []
        self._step_count = 0

        # Pending prediction state (resolved next observe() call)
        self._pending_pred:   str | None = None
        self._pending_action: int | None = None
        self._pending_conf:   float      = 0.0

        # Cumulative stats
        self.hits:           int = 0
        self.misses:         int = 0
        self.prefetches_made: int = 0
        self.prefetch_hits:  int = 0

    # ------------------------------------------------------------------
    # Main observe / predict / learn cycle
    # ------------------------------------------------------------------

    def observe(self, event: str) -> StepRecord:
        """
        Process one event from the memory trace.

        Returns a StepRecord for display.
        """
        self._step_count += 1
        rec = StepRecord()
        rec.step_n    = self._step_count
        rec.component = self.name
        rec.event     = event

        # ── 1. Resolve previous prediction ───────────────────────────
        if self._pending_pred is not None:
            hit = (self._pending_pred == event)
            if hit:
                self.hits += 1
                if self._pending_action == PREFETCH:
                    self.prefetch_hits += 1
            else:
                self.misses += 1

            reward = self.rl.learn(hit, next_conf=self._pending_conf)
            rec.hit    = hit
            rec.reward = reward

        # ── 2. Train LSTM on (context → event) ───────────────────────
        if len(self._history) >= self._window:
            ctx  = self._history[-self._window:]
            loss = self.brain.learn(ctx, event)
            rec.loss = round(loss, 4)

        # ── 3. Append to rolling history ─────────────────────────────
        self._history.append(event)

        # ── 4. Predict next + RL decision ────────────────────────────
        if len(self._history) >= self._window:
            ctx        = self._history[-self._window:]
            pred, conf = self.brain.predict(ctx)
            action_id  = self.rl.choose_action(conf)
            action_str = "PREFETCH" if action_id == PREFETCH else "WAIT"

            self._pending_pred   = pred
            self._pending_action = action_id
            self._pending_conf   = conf

            rec.pred   = pred
            rec.conf   = conf
            rec.action = action_str

            # ── 5. P2P broadcast if pre-fetching ─────────────────────
            if action_id == PREFETCH:
                self.prefetches_made += 1
                self.bus.broadcast(
                    self.name,
                    "PREFETCH_REQUEST",
                    {"predicted": pred, "confidence": round(conf, 3)},
                )

        # ── 6. Notify CPU (one-way status, no command back) ──────────
        self.cpu.receive_status(
            self.name, "event_processed", {"event": event, "step": self._step_count}
        )

        return rec

    # ------------------------------------------------------------------
    # P2P receive
    # ------------------------------------------------------------------

    def receive(self, msg: "BusMessage") -> None:
        """
        Handle incoming P2P messages from peer components.
        (In this simulation: acknowledge but do not alter own prediction
         pipeline — each brain trains independently.)
        """
        pass

    # ------------------------------------------------------------------
    # Stats / introspection
    # ------------------------------------------------------------------

    @property
    def accuracy(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0

    @property
    def prefetch_precision(self) -> float:
        return (
            self.prefetch_hits / self.prefetches_made
            if self.prefetches_made
            else 0.0
        )

    def summary(self) -> dict:
        return {
            "name":              self.name,
            "total_steps":       self._step_count,
            "hits":              self.hits,
            "misses":            self.misses,
            "accuracy":          round(self.accuracy, 4),
            "prefetches_made":   self.prefetches_made,
            "prefetch_hits":     self.prefetch_hits,
            "prefetch_precision": round(self.prefetch_precision, 4),
            "rl_epsilon":        round(self.rl.epsilon, 4),
            "rl_avg_reward":     round(self.rl.avg_reward, 4),
            "lstm_trained":      self.brain.total_trained,
            "lstm_params":       self.brain.summary()["param_count"],
        }
