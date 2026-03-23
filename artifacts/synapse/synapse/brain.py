"""
SYNAPSE Phase 6 — SynapseBrain: LSTM-based pattern prediction engine.

Each hardware component gets its own SynapseBrain — a compact LSTM network
trained online from live memory access traces.  The LSTM learns temporal
patterns in event sequences and predicts the most likely next event.

Unlike the n-gram Markov chain used in Phases 1-5, the LSTM can capture
long-range dependencies and generalises to unseen context patterns.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class _LSTMNet(nn.Module):
    """Internal PyTorch module — not used directly; go through SynapseBrain."""

    def __init__(self, vocab_size: int, embed_dim: int, hidden: int) -> None:
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.lstm  = nn.LSTM(embed_dim, hidden, batch_first=True)
        self.head  = nn.Linear(hidden, vocab_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (1, seq_len) token IDs  →  logits: (1, vocab_size)"""
        e        = self.embed(x)          # (1, seq, embed_dim)
        out, _   = self.lstm(e)           # (1, seq, hidden)
        return self.head(out[:, -1, :])   # (1, vocab_size) — last timestep only


class SynapseBrain:
    """
    LSTM prediction brain embedded in a SYNAPSE chip.

    Attributes:
        vocab:        Ordered list of distinct event/address tokens.
        vocab_size:   Number of distinct tokens.
        window:       Context window fed to the LSTM on each forward pass.
        model:        The underlying _LSTMNet.
        total_trained: Number of learn() calls made.
        last_loss:    Most recent cross-entropy loss value.
    """

    def __init__(
        self,
        vocab:      list[str],
        embed_dim:  int   = 8,
        hidden:     int   = 16,
        window:     int   = 4,
        lr:         float = 0.025,
        train_steps: int  = 4,
    ) -> None:
        self.vocab       = vocab
        self.vocab_size  = len(vocab)
        self.window      = window
        self.train_steps = train_steps

        self._tok  = {v: i for i, v in enumerate(vocab)}
        self._itok = dict(enumerate(vocab))

        self.model   = _LSTMNet(self.vocab_size, embed_dim, hidden)
        self.opt     = torch.optim.Adam(self.model.parameters(), lr=lr)
        self.loss_fn = nn.CrossEntropyLoss()

        self.total_trained = 0
        self.last_loss     = float("inf")

    # ------------------------------------------------------------------
    # Tokenisation helpers
    # ------------------------------------------------------------------

    def _enc(self, events: list[str]) -> list[int]:
        return [self._tok.get(e, 0) for e in events]

    def _dec(self, idx: int) -> str:
        return self._itok.get(idx, "?")

    # ------------------------------------------------------------------
    # Online learning
    # ------------------------------------------------------------------

    def learn(self, context: list[str], target: str) -> float:
        """
        Run `train_steps` gradient updates for one (context → target) pair.

        Args:
            context: List of recent event tokens (length == window).
            target:  The ground-truth next event token.

        Returns:
            Final cross-entropy loss after the last gradient step.
        """
        x = torch.tensor([self._enc(context)], dtype=torch.long)
        y = torch.tensor([self._tok.get(target, 0)], dtype=torch.long)

        loss_val = float("inf")
        for _ in range(self.train_steps):
            logits   = self.model(x)
            loss     = self.loss_fn(logits, y)
            self.opt.zero_grad()
            loss.backward()
            self.opt.step()
            loss_val = loss.item()

        self.total_trained += 1
        self.last_loss      = loss_val
        return loss_val

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict(self, context: list[str]) -> tuple[str, float]:
        """
        Predict the most likely next event given a context window.

        Returns:
            (predicted_event_name, confidence_0_to_1)
        """
        x = torch.tensor([self._enc(context)], dtype=torch.long)
        with torch.no_grad():
            logits = self.model(x)
            probs  = F.softmax(logits, dim=-1)
            idx    = int(probs.argmax(dim=-1).item())
            conf   = float(probs.max().item())
        return self._dec(idx), conf

    def top_k(self, context: list[str], k: int = 3) -> list[tuple[str, float]]:
        """Return the top-k predictions as (event_name, probability) pairs."""
        x = torch.tensor([self._enc(context)], dtype=torch.long)
        with torch.no_grad():
            logits      = self.model(x)
            probs       = F.softmax(logits, dim=-1).squeeze(0)
            topk_vals, topk_idxs = probs.topk(min(k, self.vocab_size))
        return [
            (self._dec(int(i)), float(p))
            for p, i in zip(topk_vals, topk_idxs)
        ]

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        total_params = sum(p.numel() for p in self.model.parameters())
        return {
            "vocab_size":    self.vocab_size,
            "window":        self.window,
            "total_trained": self.total_trained,
            "last_loss":     round(self.last_loss, 4),
            "param_count":   total_params,
        }
