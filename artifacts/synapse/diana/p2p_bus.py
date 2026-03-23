"""
DIANA Phase 6 — P2P Bus.

A zero-CPU-hop message bus that routes messages directly between Component
nodes.  Components register themselves; the CPU Observer is deliberately
NOT a peer — it receives only one-way status pushes, never bus messages.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .component import Component


@dataclass
class BusMessage:
    sender:   str
    receiver: str
    msg_type: str      # "PREFETCH_REQUEST" | "DATA_READY" | "ACK" | "SYNC"
    payload:  dict
    ts:       float = field(default_factory=time.time)


class P2PBus:
    """
    Simulated P2P hardware bus between DIANA Component nodes.

    Key design invariants (enforced by this class):
      - Zero CPU involvement in message routing.
      - All messages are logged for auditing and display.
      - Broadcast excludes the sender (no self-loops).
    """

    def __init__(self) -> None:
        self._registry: dict[str, "Component"] = {}
        self._log: list[BusMessage] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, component: "Component") -> None:
        """Add a component to the bus registry."""
        self._registry[component.name] = component

    # ------------------------------------------------------------------
    # Messaging — zero CPU hops
    # ------------------------------------------------------------------

    def send(
        self,
        sender:   str,
        receiver: str,
        msg_type: str,
        payload:  dict,
    ) -> None:
        """Deliver a message directly from sender → receiver (no CPU hop)."""
        msg = BusMessage(
            sender=sender, receiver=receiver,
            msg_type=msg_type, payload=payload,
        )
        self._log.append(msg)
        peer = self._registry.get(receiver)
        if peer is not None:
            peer.receive(msg)

    def broadcast(self, sender: str, msg_type: str, payload: dict) -> None:
        """Send the same message to all registered peers (except the sender)."""
        for name in self._registry:
            if name != sender:
                self.send(sender, name, msg_type, payload)

    # ------------------------------------------------------------------
    # Log access
    # ------------------------------------------------------------------

    def get_log(self, since: int = 0) -> list[BusMessage]:
        return self._log[since:]

    @property
    def message_count(self) -> int:
        return len(self._log)

    def log_summary(self) -> dict:
        type_counts: dict[str, int] = {}
        for m in self._log:
            type_counts[m.msg_type] = type_counts.get(m.msg_type, 0) + 1
        return {
            "total_messages": len(self._log),
            "by_type": type_counts,
            "peers_registered": list(self._registry),
        }
