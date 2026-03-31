#!/usr/bin/env python3
"""
DIANA-OS — SYNAPSE Brain (PyTorch LSTM)

Real LSTM running in userspace. Reads patterns from /proc/diana/stats,
trains on real kernel-observed patterns, writes predictions to
/proc/diana/hints. Kernel acts on high-confidence hints.

Author: Sahidh — DIANA Architecture
"""

import os
import json
import time
from pathlib import Path
from typing import List, Tuple, Optional, Dict

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("[WARN] PyTorch not installed. Install: pip install torch")


class SynapseLSTM(nn.Module):
    """LSTM network for SYNAPSE pattern prediction."""

    def __init__(self, vocab_size: int, embed_dim: int = 32,
                 hidden_dim: int = 128):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        self.lstm = nn.LSTM(embed_dim, hidden_dim, batch_first=True,
                            num_layers=2, dropout=0.1)
        self.fc = nn.Linear(hidden_dim, vocab_size)

    def forward(self, x):
        embedded = self.embedding(x)
        lstm_out, _ = self.lstm(embedded)
        last_output = lstm_out[:, -1, :]
        logits = self.fc(last_output)
        return logits


class SynapseBrain:
    """
    Real LSTM brain for a DIANA component.

    Learns event sequences and predicts the next event.
    Interfaces with kernel via /proc/diana/.
    """

    def __init__(self, name: str, vocab: List[str],
                 embed_dim: int = 32, hidden: int = 128,
                 window: int = 6, lr: float = 0.01):
        self.name = name
        self.vocab = list(vocab)
        self.vocab_to_idx = {v: i for i, v in enumerate(self.vocab)}
        self.idx_to_vocab = {i: v for i, v in enumerate(self.vocab)}
        self.window = window
        self.embed_dim = embed_dim
        self.hidden = hidden

        if not TORCH_AVAILABLE:
            self.model = None
            self.optimizer = None
            self.criterion = None
            return

        self.model = SynapseLSTM(len(self.vocab), embed_dim, hidden)
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)
        self.criterion = nn.CrossEntropyLoss()

        # Training stats
        self.total_trains = 0
        self.total_predictions = 0
        self.correct_predictions = 0
        self.last_loss = 0.0

    def _encode(self, events: List[str]) -> Optional[torch.Tensor]:
        """Convert event names to tensor indices."""
        if not TORCH_AVAILABLE:
            return None
        indices = []
        for e in events:
            if e in self.vocab_to_idx:
                indices.append(self.vocab_to_idx[e])
            else:
                # Add to vocab dynamically
                idx = len(self.vocab)
                self.vocab.append(e)
                self.vocab_to_idx[e] = idx
                self.idx_to_vocab[idx] = e
                # Resize model embedding
                old_embed = self.model.embedding
                new_embed = nn.Embedding(len(self.vocab), self.embed_dim)
                with torch.no_grad():
                    new_embed.weight[:old_embed.num_embeddings] = \
                        old_embed.weight
                self.model.embedding = new_embed
                # Resize output layer
                old_fc = self.model.fc
                new_fc = nn.Linear(self.hidden, len(self.vocab))
                with torch.no_grad():
                    new_fc.weight[:old_fc.out_features] = old_fc.weight
                    new_fc.bias[:old_fc.out_features] = old_fc.bias
                self.model.fc = new_fc
                # Update optimizer
                self.optimizer = optim.Adam(self.model.parameters(),
                                           lr=self.optimizer.defaults['lr'])
                indices.append(idx)
        return torch.tensor([indices], dtype=torch.long)

    def learn(self, context: List[str], target: str) -> float:
        """
        Train on a single example.
        Returns: loss value
        """
        if not TORCH_AVAILABLE or self.model is None:
            return 0.0

        context_tensor = self._encode(context)
        if context_tensor is None:
            return 0.0

        # Ensure target is in vocab
        if target not in self.vocab_to_idx:
            self._encode([target])
        target_idx = torch.tensor([self.vocab_to_idx[target]],
                                  dtype=torch.long)

        self.model.train()
        self.optimizer.zero_grad()

        logits = self.model(context_tensor)
        loss = self.criterion(logits, target_idx)
        loss.backward()
        self.optimizer.step()

        self.total_trains += 1
        self.last_loss = loss.item()

        return loss.item()

    def predict(self, context: List[str]) -> Tuple[str, float]:
        """
        Predict the next event given context.
        Returns: (predicted_event, confidence)
        """
        if not TORCH_AVAILABLE or self.model is None:
            return (self.vocab[0] if self.vocab else "", 0.0)

        context_tensor = self._encode(context)
        if context_tensor is None:
            return (self.vocab[0], 0.0)

        self.model.eval()
        with torch.no_grad():
            logits = self.model(context_tensor)
            probs = torch.softmax(logits, dim=-1)
            confidence, idx = torch.max(probs, dim=-1)

        self.total_predictions += 1
        predicted = self.idx_to_vocab.get(idx.item(), "unknown")

        return (predicted, confidence.item())

    def read_kernel_patterns(self, proc_path: str = "/proc/diana") \
            -> List[Dict]:
        """Read patterns from /proc/diana/stats."""
        stats_path = os.path.join(proc_path, "stats")
        patterns = []

        try:
            with open(stats_path, 'r') as f:
                content = f.read()
            # Parse component sections
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('[') and 'SYNAPSE' in line:
                    component = line.strip('[]').split()[0]
                    patterns.append({
                        'component': component,
                        'raw': line
                    })
                elif ':' in line and patterns:
                    key, _, value = line.partition(':')
                    patterns[-1][key.strip()] = value.strip()
        except FileNotFoundError:
            pass
        except PermissionError:
            pass

        return patterns

    def write_kernel_hints(self, component: str, event: str,
                           confidence: float,
                           proc_path: str = "/proc/diana") -> bool:
        """
        Write prediction to /proc/diana/hints.
        Only writes if confidence > 0.70.
        Format: "COMPONENT:EVENT:CONFIDENCE\n"
        """
        if confidence < 0.70:
            return False

        hints_path = os.path.join(proc_path, "hints")
        conf_int = int(confidence * 1000)
        hint = f"{component}:{event}:{conf_int}\n"

        try:
            with open(hints_path, 'w') as f:
                f.write(hint)
            return True
        except (FileNotFoundError, PermissionError):
            return False

    def train_from_kernel_data(self,
                                proc_path: str = "/proc/diana") -> Dict:
        """
        Read real patterns from kernel, train LSTM, write hints back.
        Returns training summary.
        """
        patterns = self.read_kernel_patterns(proc_path)
        results = {
            'patterns_read': len(patterns),
            'hints_written': 0,
            'avg_loss': 0.0,
        }

        if not patterns:
            return results

        # Build sequence from patterns
        events = [p.get('component', 'UNK') for p in patterns]

        total_loss = 0.0
        count = 0

        for i in range(len(events) - self.window):
            context = events[i:i + self.window]
            target = events[i + self.window]
            loss = self.learn(context, target)
            total_loss += loss
            count += 1

        if count > 0:
            results['avg_loss'] = total_loss / count

        # Make predictions and write high-confidence hints
        if len(events) >= self.window:
            context = events[-self.window:]
            pred, conf = self.predict(context)

            if self.write_kernel_hints(self.name, pred, conf, proc_path):
                results['hints_written'] = 1

        return results

    def save(self, path: str) -> None:
        """Save model state to disk."""
        if not TORCH_AVAILABLE or self.model is None:
            return

        state = {
            'model_state': self.model.state_dict(),
            'optimizer_state': self.optimizer.state_dict(),
            'vocab': self.vocab,
            'name': self.name,
            'embed_dim': self.embed_dim,
            'hidden': self.hidden,
            'window': self.window,
            'total_trains': self.total_trains,
            'total_predictions': self.total_predictions,
            'correct_predictions': self.correct_predictions,
        }
        torch.save(state, path)

    def load(self, path: str) -> bool:
        """Load model state from disk."""
        if not TORCH_AVAILABLE:
            return False

        try:
            state = torch.load(path, weights_only=False)

            self.vocab = state['vocab']
            self.vocab_to_idx = {v: i for i, v in enumerate(self.vocab)}
            self.idx_to_vocab = {i: v for i, v in enumerate(self.vocab)}
            self.embed_dim = state.get('embed_dim', 32)
            self.hidden = state.get('hidden', 128)

            self.model = SynapseLSTM(len(self.vocab), self.embed_dim,
                                     self.hidden)
            self.model.load_state_dict(state['model_state'])
            self.optimizer = optim.Adam(self.model.parameters())
            self.optimizer.load_state_dict(state['optimizer_state'])

            self.total_trains = state.get('total_trains', 0)
            self.total_predictions = state.get('total_predictions', 0)
            self.correct_predictions = state.get('correct_predictions', 0)

            return True
        except (FileNotFoundError, Exception) as e:
            print(f"[{self.name}] Failed to load model: {e}")
            return False

    def summary(self) -> Dict:
        """Get brain summary statistics."""
        accuracy = 0.0
        if self.total_predictions > 0:
            accuracy = self.correct_predictions / self.total_predictions

        return {
            'name': self.name,
            'vocab_size': len(self.vocab),
            'total_trains': self.total_trains,
            'total_predictions': self.total_predictions,
            'correct_predictions': self.correct_predictions,
            'accuracy': accuracy,
            'last_loss': self.last_loss,
            'torch_available': TORCH_AVAILABLE,
        }


if __name__ == '__main__':
    # Quick self-test
    print("=== SYNAPSE Brain Self-Test ===")

    vocab = ['chrome', 'vscode', 'terminal', 'browser', 'game']
    brain = SynapseBrain("TEST", vocab, embed_dim=16, hidden=32)

    # Train
    for _ in range(50):
        brain.learn(['chrome', 'vscode', 'terminal', 'chrome'], 'browser')

    # Predict
    pred, conf = brain.predict(['chrome', 'vscode', 'terminal', 'chrome'])
    print(f"Predicted: {pred} (confidence: {conf:.2%})")
    print(f"Summary: {json.dumps(brain.summary(), indent=2)}")
