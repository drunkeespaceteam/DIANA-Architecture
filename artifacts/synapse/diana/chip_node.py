"""
ChipNode — an intelligent hardware component in the DIANA Architecture.

Each ChipNode:
  - Wraps a SynapseChip for independent pattern learning
  - Maintains direct P2P connections to other ChipNodes (no central controller)
  - Can subscribe to another node's message stream (passive observation)
  - Reports status updates to the CPUReporter (one-way)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional

from synapse.core import SynapseChip

if TYPE_CHECKING:
    from .cpu_reporter import CPUReporter


@dataclass
class Message:
    sender: str
    receiver: str
    content: str
    msg_type: str           # "alert" | "ready" | "preload" | "observe" | "status"
    timestamp: float = field(default_factory=time.time)
    reasoning: Optional[str] = None


# Global conversation log — every sent/received message lands here
_conversation: list[Message] = []


def get_conversation() -> list[Message]:
    return list(_conversation)


def clear_conversation() -> None:
    _conversation.clear()


class ChipNode:
    """
    A hardware-intelligence node in the DIANA P2P network.

    Attributes:
        name:         Display name, e.g. "SSD", "GPU", "RAM"
        chip:         Underlying SynapseChip for pattern learning
        peers:        Direct connections to other ChipNodes {name: ChipNode}
        subscribers:  Callables invoked whenever this node receives a message
        cpu:          Optional CPUReporter reference (send-only, never receive)
    """

    def __init__(
        self,
        name: str,
        order: int = 2,
        cpu: Optional["CPUReporter"] = None,
    ) -> None:
        self.name = name
        self.chip = SynapseChip(order=order)
        self.peers: dict[str, "ChipNode"] = {}
        self.subscribers: list[Callable[[Message], None]] = []
        self.cpu = cpu

    # ------------------------------------------------------------------
    # P2P Connectivity
    # ------------------------------------------------------------------

    def connect(self, *nodes: "ChipNode") -> None:
        """Establish direct P2P links to other ChipNodes (bidirectional)."""
        for node in nodes:
            self.peers[node.name] = node
            node.peers[self.name] = self

    def subscribe(self, target: "ChipNode") -> None:
        """
        Silently observe all messages received by `target`.
        This is how RAM can hear GPU/SSD conversations without being addressed.
        """
        target.subscribers.append(self._on_observed_message)

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    def send(
        self,
        to: str,
        content: str,
        msg_type: str = "alert",
        reasoning: str | None = None,
    ) -> None:
        """Send a message directly to a peer by name."""
        peer = self.peers.get(to)
        if peer is None:
            raise ValueError(
                f"{self.name} has no P2P connection to '{to}'. "
                f"Available peers: {list(self.peers)}"
            )
        msg = Message(
            sender=self.name,
            receiver=to,
            content=content,
            msg_type=msg_type,
            reasoning=reasoning,
        )
        _conversation.append(msg)
        peer.receive(msg)

    def receive(self, msg: Message) -> None:
        """Process an incoming message and fire subscriber callbacks."""
        # Let all passive observers see this message
        for callback in self.subscribers:
            callback(msg)

    def _on_observed_message(self, msg: Message) -> None:
        """
        Called when a subscribed-to node receives a message.
        Logged as an observation in the conversation.
        """
        observe_msg = Message(
            sender=self.name,
            receiver="*",
            content=f"(overheard: {msg.sender} → {msg.receiver}: \"{msg.content}\")",
            msg_type="observe",
        )
        _conversation.append(observe_msg)

    def broadcast_status(self, status: str) -> None:
        """Send a one-way status notification to the CPU Reporter."""
        if self.cpu is not None:
            self.cpu.notify(self.name, status)
        msg = Message(
            sender=self.name,
            receiver="CPU",
            content=status,
            msg_type="status",
        )
        _conversation.append(msg)

    # ------------------------------------------------------------------
    # Intelligence — observe an event, predict next, optionally react
    # ------------------------------------------------------------------

    def observe_event(self, event: str) -> Optional[str]:
        """
        Record an event into this chip's memory and return its prediction
        for what comes next (or None if not enough data).
        """
        self.chip.observe(event)
        return self.chip.predict()

    def train(self, sequence: list[str]) -> None:
        """Batch-train this chip's underlying pattern engine."""
        self.chip.train(sequence)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        return {
            "name": self.name,
            "peers": list(self.peers),
            **self.chip.summary(),
        }
