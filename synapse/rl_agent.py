#!/usr/bin/env python3
"""
DIANA-OS — Reinforcement Learning Agent

Q-Learning agent for prefetch/wait decisions.
Learns optimal thresholds for when to prefetch based on
SYNAPSE confidence scores and outcome feedback.

Author: Sahidh — DIANA Architecture
"""

import os
import json
import random
from typing import Dict, Optional

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class RLAgent:
    """
    Q-Learning agent for DIANA prefetch decisions.

    State: discretized confidence level (0-10)
    Actions: 0 = WAIT, 1 = PREFETCH
    """

    # Actions
    ACTION_WAIT = 0
    ACTION_PREFETCH = 1
    NUM_ACTIONS = 2

    # State: confidence buckets (0-10)
    NUM_STATES = 11

    def __init__(self, name: str, alpha: float = 0.1,
                 gamma: float = 0.95, epsilon: float = 1.0,
                 epsilon_decay: float = 0.995,
                 epsilon_min: float = 0.01):
        self.name = name
        self.alpha = alpha        # Learning rate
        self.gamma = gamma        # Discount factor
        self.epsilon = epsilon    # Exploration rate
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min

        # Q-table: state x action
        self.q_table = [[0.0] * self.NUM_ACTIONS
                        for _ in range(self.NUM_STATES)]

        # Stats
        self.total_decisions = 0
        self.prefetch_count = 0
        self.wait_count = 0
        self.correct_prefetches = 0
        self.incorrect_prefetches = 0
        self.total_reward = 0.0
        self.last_state = 0
        self.last_action = 0

    def _confidence_to_state(self, confidence: float) -> int:
        """Map confidence [0.0, 1.0] to state [0, 10]."""
        state = int(confidence * 10)
        return max(0, min(self.NUM_STATES - 1, state))

    def choose_action(self, confidence: float) -> int:
        """
        Choose WAIT or PREFETCH based on confidence.
        Uses epsilon-greedy exploration.
        """
        state = self._confidence_to_state(confidence)
        self.last_state = state

        # Epsilon-greedy
        if random.random() < self.epsilon:
            action = random.randint(0, self.NUM_ACTIONS - 1)
        else:
            # Greedy: pick action with highest Q-value
            if self.q_table[state][self.ACTION_PREFETCH] > \
               self.q_table[state][self.ACTION_WAIT]:
                action = self.ACTION_PREFETCH
            elif self.q_table[state][self.ACTION_PREFETCH] < \
                 self.q_table[state][self.ACTION_WAIT]:
                action = self.ACTION_WAIT
            else:
                action = random.randint(0, self.NUM_ACTIONS - 1)

        self.last_action = action
        self.total_decisions += 1

        if action == self.ACTION_PREFETCH:
            self.prefetch_count += 1
        else:
            self.wait_count += 1

        return action

    def learn(self, was_correct: bool, next_confidence: float) -> float:
        """
        Update Q-table based on outcome.

        Args:
            was_correct: whether the prefetch/wait decision was right
            next_confidence: confidence for the next state

        Returns:
            reward given
        """
        # Reward structure
        if self.last_action == self.ACTION_PREFETCH:
            if was_correct:
                reward = 1.0    # Correct prefetch — great!
                self.correct_prefetches += 1
            else:
                reward = -0.5   # Wasted prefetch — bad
                self.incorrect_prefetches += 1
        else:  # WAIT
            if was_correct:
                reward = 0.3    # Correctly waited — okay
            else:
                reward = -0.3   # Should have prefetched — missed opportunity

        next_state = self._confidence_to_state(next_confidence)

        # Q-learning update
        old_q = self.q_table[self.last_state][self.last_action]
        max_next_q = max(self.q_table[next_state])

        new_q = old_q + self.alpha * (
            reward + self.gamma * max_next_q - old_q
        )
        self.q_table[self.last_state][self.last_action] = new_q

        # Decay epsilon
        self.epsilon = max(self.epsilon_min,
                          self.epsilon * self.epsilon_decay)

        self.total_reward += reward

        return reward

    def read_kernel_feedback(self, proc_path: str = "/proc/diana") -> bool:
        """
        Read from /proc/diana/stats to determine if last prefetch
        was a hit or miss.
        """
        stats_path = os.path.join(proc_path, "stats")
        try:
            with open(stats_path, 'r') as f:
                content = f.read()
            # Look for prefetch_hits in stats
            for line in content.split('\n'):
                if 'prefetch_hits' in line.lower():
                    parts = line.split(':')
                    if len(parts) >= 2:
                        try:
                            hits = int(parts[-1].strip().split('/')[0]
                                      .strip())
                            return hits > 0
                        except ValueError:
                            pass
        except (FileNotFoundError, PermissionError):
            pass

        return False

    def get_policy_summary(self) -> Dict[int, str]:
        """Return the learned policy: state -> best action."""
        policy = {}
        for state in range(self.NUM_STATES):
            if self.q_table[state][self.ACTION_PREFETCH] > \
               self.q_table[state][self.ACTION_WAIT]:
                policy[state] = "PREFETCH"
            elif self.q_table[state][self.ACTION_PREFETCH] < \
                 self.q_table[state][self.ACTION_WAIT]:
                policy[state] = "WAIT"
            else:
                policy[state] = "UNDECIDED"
        return policy

    def save(self, path: str) -> None:
        """Save agent state to disk."""
        state = {
            'name': self.name,
            'q_table': self.q_table,
            'epsilon': self.epsilon,
            'alpha': self.alpha,
            'gamma': self.gamma,
            'total_decisions': self.total_decisions,
            'prefetch_count': self.prefetch_count,
            'wait_count': self.wait_count,
            'correct_prefetches': self.correct_prefetches,
            'incorrect_prefetches': self.incorrect_prefetches,
            'total_reward': self.total_reward,
        }
        with open(path, 'w') as f:
            json.dump(state, f, indent=2)

    def load(self, path: str) -> bool:
        """Load agent state from disk."""
        try:
            with open(path, 'r') as f:
                state = json.load(f)

            self.q_table = state['q_table']
            self.epsilon = state.get('epsilon', self.epsilon)
            self.total_decisions = state.get('total_decisions', 0)
            self.prefetch_count = state.get('prefetch_count', 0)
            self.wait_count = state.get('wait_count', 0)
            self.correct_prefetches = state.get('correct_prefetches', 0)
            self.incorrect_prefetches = state.get('incorrect_prefetches', 0)
            self.total_reward = state.get('total_reward', 0.0)
            return True
        except (FileNotFoundError, json.JSONDecodeError):
            return False

    def summary(self) -> Dict:
        """Get agent summary."""
        accuracy = 0.0
        total_pf = self.correct_prefetches + self.incorrect_prefetches
        if total_pf > 0:
            accuracy = self.correct_prefetches / total_pf

        return {
            'name': self.name,
            'total_decisions': self.total_decisions,
            'prefetch_count': self.prefetch_count,
            'wait_count': self.wait_count,
            'correct_prefetches': self.correct_prefetches,
            'incorrect_prefetches': self.incorrect_prefetches,
            'prefetch_accuracy': accuracy,
            'epsilon': self.epsilon,
            'total_reward': self.total_reward,
            'policy': self.get_policy_summary(),
        }


if __name__ == '__main__':
    # Quick self-test
    print("=== RL Agent Self-Test ===")

    agent = RLAgent("TEST")

    # Simulate decisions
    for i in range(200):
        conf = random.uniform(0.0, 1.0)
        action = agent.choose_action(conf)
        # Simulate: high confidence prefetches tend to be correct
        was_correct = (action == 1 and conf > 0.6) or \
                     (action == 0 and conf < 0.4)
        agent.learn(was_correct, random.uniform(0.0, 1.0))

    print(f"Summary: {json.dumps(agent.summary(), indent=2)}")
