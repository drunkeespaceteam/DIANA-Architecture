#!/usr/bin/env python3
"""
DIANA-OS — Userspace Training Daemon

Bridges kernel intelligence and LSTM.
Runs continuously as a system service.

Cycle (every 5 seconds):
  1. Read kernel patterns from /proc/diana/stats
  2. Train each component brain
  3. Make predictions
  4. Write hints to /proc/diana/hints
  5. Read P2P log from /proc/diana/p2p_log
  6. Update RL with outcomes
  7. Save models periodically

Author: Sahidh — DIANA Architecture
"""

import os
import sys
import time
import signal
import logging
import argparse
from pathlib import Path
from typing import Dict, List

# Add parent dir for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synapse.brain import SynapseBrain
from synapse.rl_agent import RLAgent


# Component vocabularies (kernel event types)
COMPONENT_VOCABS = {
    'RAM': ['kmalloc_small', 'kmalloc_med', 'kmalloc_large',
            'page_fault', 'mmap', 'munmap', 'pressure_low',
            'pressure_med', 'pressure_high', 'prefetch_hit',
            'prefetch_miss'],
    'GPU': ['process_switch', 'render_start', 'render_end',
            'buffer_alloc', 'texture_load', 'shader_compile',
            'vsync', 'compute_start', 'compute_end',
            'prefetch_hit', 'prefetch_miss'],
    'SSD': ['read_small', 'read_med', 'read_large',
            'write_small', 'write_med', 'write_large',
            'open', 'close', 'seek', 'prefetch_hit',
            'prefetch_miss', 'sequential', 'random'],
    'CACHE': ['hit', 'miss', 'eviction', 'inode_lookup',
              'inode_create', 'inode_evict', 'dentry_lookup',
              'page_hit', 'page_miss', 'prefetch_hit',
              'prefetch_miss'],
}

LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'


class DIANATrainer:
    """
    Userspace training daemon for DIANA-OS.
    Creates and manages SYNAPSE brains for each hardware component.
    """

    def __init__(self, proc_path: str = "/proc/diana",
                 model_dir: str = "/var/lib/diana/models",
                 log_file: str = "/var/log/diana_trainer.log"):
        self.proc_path = proc_path
        self.model_dir = model_dir
        self.log_file = log_file
        self.running = False

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format=LOG_FORMAT,
            handlers=[
                logging.StreamHandler(sys.stdout),
            ]
        )
        self.logger = logging.getLogger('DIANA-Trainer')

        # Try to add file handler
        try:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            fh = logging.FileHandler(log_file)
            fh.setFormatter(logging.Formatter(LOG_FORMAT))
            self.logger.addHandler(fh)
        except PermissionError:
            self.logger.warning(f"Cannot write to {log_file}, "
                              "logging to stdout only")

        # Create model directory
        try:
            os.makedirs(model_dir, exist_ok=True)
        except PermissionError:
            self.model_dir = '/tmp/diana_models'
            os.makedirs(self.model_dir, exist_ok=True)
            self.logger.warning(f"Using {self.model_dir} for models")

        # Initialize brains and RL agents for each component
        self.brains: Dict[str, SynapseBrain] = {}
        self.agents: Dict[str, RLAgent] = {}

        for comp, vocab in COMPONENT_VOCABS.items():
            self.brains[comp] = SynapseBrain(
                comp, vocab,
                embed_dim=32, hidden=128, window=6, lr=0.01
            )
            self.agents[comp] = RLAgent(comp)

            # Try to load existing models
            brain_path = os.path.join(self.model_dir, f'{comp}_brain.pt')
            agent_path = os.path.join(self.model_dir, f'{comp}_agent.json')

            if os.path.exists(brain_path):
                self.brains[comp].load(brain_path)
                self.logger.info(f"Loaded {comp} brain from {brain_path}")
            if os.path.exists(agent_path):
                self.agents[comp].load(agent_path)
                self.logger.info(f"Loaded {comp} agent from {agent_path}")

        self.logger.info("DIANA Trainer initialized with components: "
                        f"{list(self.brains.keys())}")

        # Cycle counter
        self.cycle = 0

    def read_kernel_stats(self) -> Dict[str, Dict]:
        """Read /proc/diana/stats and parse per-component data."""
        stats = {}
        stats_path = os.path.join(self.proc_path, 'stats')

        try:
            with open(stats_path, 'r') as f:
                content = f.read()

            current_component = None
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('[') and 'SYNAPSE' in line:
                    current_component = line.strip('[]').split()[0]
                    stats[current_component] = {}
                elif ':' in line and current_component:
                    key, _, value = line.partition(':')
                    stats[current_component][key.strip()] = value.strip()
        except (FileNotFoundError, PermissionError):
            pass

        return stats

    def read_p2p_log(self) -> List[str]:
        """Read /proc/diana/p2p_log."""
        log_path = os.path.join(self.proc_path, 'p2p_log')
        try:
            with open(log_path, 'r') as f:
                return f.readlines()
        except (FileNotFoundError, PermissionError):
            return []

    def write_hint(self, component: str, event: str,
                   confidence: float) -> bool:
        """Write a hint to /proc/diana/hints."""
        if confidence < 0.70:
            return False

        hints_path = os.path.join(self.proc_path, 'hints')
        conf_int = int(confidence * 1000)
        hint = f"{component}:{event}:{conf_int}\n"

        try:
            with open(hints_path, 'w') as f:
                f.write(hint)
            self.logger.debug(f"Hint written: {hint.strip()}")
            return True
        except (FileNotFoundError, PermissionError):
            return False

    def training_cycle(self):
        """
        One training cycle:
        1. Read kernel patterns
        2. Train each component brain
        3. Make predictions
        4. Write hints
        5. Read P2P log
        6. Update RL
        7. Save periodically
        """
        self.cycle += 1
        self.logger.info(f"--- Cycle {self.cycle} ---")

        # Step 1: Read kernel stats
        stats = self.read_kernel_stats()

        # Step 2-4: Train, predict, hint for each component
        for comp_name, brain in self.brains.items():
            # Get patterns from kernel data
            result = brain.train_from_kernel_data(self.proc_path)

            if result['patterns_read'] > 0:
                self.logger.info(
                    f"[{comp_name}] trained on {result['patterns_read']} "
                    f"patterns, avg_loss={result['avg_loss']:.4f}"
                )

            # RL decision on whether to prefetch
            agent = self.agents[comp_name]
            summary = brain.summary()

            # Use brain accuracy as confidence
            confidence = summary.get('accuracy', 0.0)
            action = agent.choose_action(confidence)

            if action == RLAgent.ACTION_PREFETCH:
                # Make a prediction and write hint
                vocab = COMPONENT_VOCABS[comp_name]
                if len(vocab) >= brain.window:
                    context = vocab[:brain.window]
                    pred, conf = brain.predict(context)
                    if self.write_hint(comp_name, pred, conf):
                        self.logger.info(
                            f"[{comp_name}] PREFETCH hint: {pred} "
                            f"(conf: {conf:.2%})"
                        )

        # Step 5: Read P2P log
        p2p_messages = self.read_p2p_log()
        if p2p_messages:
            self.logger.info(f"P2P log: {len(p2p_messages)} messages")

        # Step 6: Update RL with feedback
        for comp_name, agent in self.agents.items():
            was_correct = agent.read_kernel_feedback(self.proc_path)
            agent.learn(was_correct, 0.5)

        # Step 7: Save models every 10 cycles
        if self.cycle % 10 == 0:
            self.save_all_models()

    def save_all_models(self):
        """Save all brain and agent models."""
        for comp_name in self.brains:
            brain_path = os.path.join(self.model_dir,
                                      f'{comp_name}_brain.pt')
            agent_path = os.path.join(self.model_dir,
                                      f'{comp_name}_agent.json')
            self.brains[comp_name].save(brain_path)
            self.agents[comp_name].save(agent_path)

        self.logger.info("All models saved")

    def training_loop(self, interval: float = 5.0):
        """Run training cycles continuously."""
        self.running = True

        while self.running:
            try:
                self.training_cycle()
            except Exception as e:
                self.logger.error(f"Training cycle error: {e}")

            time.sleep(interval)

    def stop(self):
        """Stop the training loop."""
        self.running = False
        self.save_all_models()
        self.logger.info("DIANA Trainer stopped")

    def start_as_daemon(self):
        """Fork and run as daemon process."""
        # Double-fork to daemonize
        try:
            pid = os.fork()
            if pid > 0:
                print(f"DIANA Trainer daemon started (PID: {pid})")
                sys.exit(0)
        except OSError as e:
            print(f"Fork #1 failed: {e}")
            sys.exit(1)
        except AttributeError:
            # os.fork not available on Windows
            print("Daemon mode not available on Windows. "
                  "Running in foreground.")
            self.training_loop()
            return

        os.setsid()

        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as e:
            sys.exit(1)

        # Redirect stdio
        sys.stdout.flush()
        sys.stderr.flush()

        # Write PID file
        pid_file = '/var/run/diana_trainer.pid'
        try:
            with open(pid_file, 'w') as f:
                f.write(str(os.getpid()))
        except PermissionError:
            pid_file = '/tmp/diana_trainer.pid'
            with open(pid_file, 'w') as f:
                f.write(str(os.getpid()))

        self.logger.info(f"Daemon running (PID: {os.getpid()})")
        self.training_loop()


def main():
    parser = argparse.ArgumentParser(
        description='DIANA-OS SYNAPSE Training Daemon'
    )
    parser.add_argument('--daemon', action='store_true',
                       help='Run as background daemon')
    parser.add_argument('--test-mode', action='store_true',
                       help='Run 3 cycles then exit (for testing)')
    parser.add_argument('--proc-path', default='/proc/diana',
                       help='Path to DIANA proc interface')
    parser.add_argument('--model-dir', default='/var/lib/diana/models',
                       help='Directory for model storage')
    parser.add_argument('--interval', type=float, default=5.0,
                       help='Training interval in seconds')

    args = parser.parse_args()

    trainer = DIANATrainer(
        proc_path=args.proc_path,
        model_dir=args.model_dir,
    )

    # Handle signals gracefully
    def signal_handler(signum, frame):
        trainer.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    if args.test_mode:
        print("=== DIANA Trainer — Test Mode ===")
        for i in range(3):
            trainer.training_cycle()
            time.sleep(1)
        trainer.save_all_models()
        print("=== Test complete ===")
    elif args.daemon:
        trainer.start_as_daemon()
    else:
        print("╔═══════════════════════════════════════╗")
        print("║  DIANA-OS SYNAPSE Training Daemon     ║")
        print("║  Press Ctrl+C to stop                 ║")
        print("╚═══════════════════════════════════════╝")
        trainer.training_loop(interval=args.interval)


if __name__ == '__main__':
    main()
