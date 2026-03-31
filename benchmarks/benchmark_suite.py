#!/usr/bin/env python3
"""
DIANA-OS — Benchmark Suite Orchestrator

Runs the complete benchmark comparison:
  1. Baseline (standard Linux, no DIANA modules)
  2. DIANA (with modules loaded + LSTM warmup)
  3. Generates comparison report with real data

Usage:
  python3 benchmarks/benchmark_suite.py                  # Full run
  python3 benchmarks/benchmark_suite.py --quick           # Quick run (~2 min)
  python3 benchmarks/benchmark_suite.py --baseline-only   # Only baseline
  python3 benchmarks/benchmark_suite.py --diana-only      # Only DIANA
  python3 benchmarks/benchmark_suite.py --compare FILE1 FILE2

Author: Sahidh — DIANA Architecture
"""

import os
import sys
import json
import time
import subprocess
import signal
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmarks.workloads import (
    run_all_workloads, read_diana_stats, snapshot_metrics
)
from benchmarks.report_generator import BenchmarkReport


# ════════════════════════════════════════════════════════════════
# Configuration
# ════════════════════════════════════════════════════════════════

RESULTS_DIR = '/tmp/diana_benchmark/results'
MODULE_PATH = None  # Auto-detected
DIANA_TRAINER = None  # Auto-detected
WARMUP_SECONDS = 60  # How long DIANA LSTM learns before measuring


def find_project_root() -> str:
    """Find the DIANA-OS project root directory."""
    # Try relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    if os.path.exists(os.path.join(project_dir, 'kernel')):
        return project_dir

    # Try common locations
    for path in ['/root/DIANA-OS', os.path.expanduser('~/DIANA-OS'),
                 '/mnt/c/Users/*/DIANA-OS']:
        import glob
        matches = glob.glob(path)
        if matches and os.path.exists(os.path.join(matches[0], 'kernel')):
            return matches[0]

    return project_dir


def detect_paths():
    """Auto-detect module and trainer paths."""
    global MODULE_PATH, DIANA_TRAINER
    root = find_project_root()
    MODULE_PATH = os.path.join(root, 'kernel', 'diana_core.ko')
    DIANA_TRAINER = os.path.join(root, 'userspace', 'diana_trainer.py')


# ════════════════════════════════════════════════════════════════
# Module Management (SAFE — never touches host OS)
# ════════════════════════════════════════════════════════════════

def is_diana_loaded() -> bool:
    """Check if DIANA kernel module is currently loaded."""
    return os.path.exists('/proc/diana/stats')


def load_diana_module() -> bool:
    """Load DIANA kernel module (requires root)."""
    if is_diana_loaded():
        print("  DIANA module already loaded")
        return True

    if not os.path.exists(MODULE_PATH):
        print(f"  ✗ Module not found: {MODULE_PATH}")
        print("  Run: make module")
        return False

    print(f"  Loading {MODULE_PATH}...")
    result = subprocess.run(
        ['sudo', 'insmod', MODULE_PATH],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"  ✗ insmod failed: {result.stderr.strip()}")
        return False

    # Verify
    time.sleep(1)
    if is_diana_loaded():
        print("  ✓ DIANA module loaded — /proc/diana/ active")
        return True
    else:
        print("  ✗ Module loaded but /proc/diana/ not found")
        return False


def unload_diana_module() -> bool:
    """Unload DIANA kernel module."""
    if not is_diana_loaded():
        return True

    print("  Unloading DIANA module...")
    result = subprocess.run(
        ['sudo', 'rmmod', 'diana_core'],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"  ⚠ rmmod failed: {result.stderr.strip()}")
        return False

    time.sleep(1)
    print("  ✓ DIANA module unloaded")
    return True


def start_diana_trainer() -> Optional[subprocess.Popen]:
    """Start the DIANA LSTM trainer daemon."""
    if not os.path.exists(DIANA_TRAINER):
        print(f"  ⚠ Trainer not found: {DIANA_TRAINER}")
        return None

    print("  Starting DIANA LSTM trainer daemon...")
    proc = subprocess.Popen(
        ['python3', DIANA_TRAINER],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(2)

    if proc.poll() is None:
        print(f"  ✓ Trainer running (PID: {proc.pid})")
        return proc
    else:
        print(f"  ⚠ Trainer exited early")
        return None


def stop_diana_trainer(proc: Optional[subprocess.Popen]):
    """Stop the DIANA LSTM trainer daemon."""
    if proc and proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)
        print(f"  ✓ Trainer stopped")


# ════════════════════════════════════════════════════════════════
# Benchmark Runs
# ════════════════════════════════════════════════════════════════

def run_baseline(quick: bool = False) -> Dict:
    """
    Run benchmarks WITHOUT DIANA modules.
    This measures the standard Linux kernel performance.
    """
    print("")
    print("╔══════════════════════════════════════════════════════╗")
    print("║  BASELINE — Standard Linux Kernel (No DIANA)        ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("")

    # Ensure DIANA is NOT loaded
    if is_diana_loaded():
        print("  Unloading DIANA module for baseline measurement...")
        if not unload_diana_module():
            print("  ⚠ Could not unload DIANA — baseline may be skewed")

    print("  Running workloads on STANDARD Linux kernel...")
    print("  Every measurement reads real /proc metrics")
    print("")

    results = run_all_workloads(quick=quick)
    results['mode'] = 'baseline'
    results['description'] = 'Standard Linux kernel — no DIANA SYNAPSE modules'

    # Save results
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath = os.path.join(RESULTS_DIR, f'baseline_{timestamp}.json')
    with open(filepath, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved: {filepath}")

    return results


def run_diana(quick: bool = False, warmup: int = None) -> Dict:
    """
    Run benchmarks WITH DIANA modules loaded.
    This measures the DIANA Architecture performance.
    """
    if warmup is None:
        warmup = 10 if quick else WARMUP_SECONDS

    print("")
    print("╔══════════════════════════════════════════════════════╗")
    print("║  DIANA — SYNAPSE Intelligence Active                ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("")

    # Load DIANA module
    if not is_diana_loaded():
        if not load_diana_module():
            print("  ✗ Cannot run DIANA benchmark without module!")
            print("  Build first: make module")
            return {'mode': 'diana', 'error': 'Module not available'}

    # Start LSTM trainer
    trainer_proc = start_diana_trainer()

    # Warmup — let DIANA learn system patterns
    print(f"\n  ═══ DIANA WARMUP ({warmup}s) ═══")
    print("  SYNAPSE is learning your system's patterns...")
    print("  The LSTM trains on real kernel data during this time.")
    print("")

    for remaining in range(warmup, 0, -1):
        sys.stdout.write(f'\r  ⏳ Warmup: {remaining}s remaining...')
        sys.stdout.flush()

        # Read DIANA stats periodically to show it's learning
        if remaining % 10 == 0 and remaining != warmup:
            stats = read_diana_stats()
            if stats.get('diana_loaded'):
                p2p = stats.get('total_messages', '?')
                sys.stdout.write(
                    f'\r  ⏳ Warmup: {remaining}s — P2P messages: {p2p}    ')

        time.sleep(1)

    print(f'\r  ✓ Warmup complete — DIANA SYNAPSE is trained          ')
    print("")

    # Show DIANA status
    stats = read_diana_stats()
    if stats.get('diana_loaded'):
        print("  DIANA Status After Warmup:")
        for key in ['total_messages', 'commands_issued']:
            if key in stats:
                print(f"    {key}: {stats[key]}")
    print("")

    print("  Running workloads with DIANA SYNAPSE active...")
    print("  Every measurement reads real /proc + /proc/diana metrics")
    print("")

    results = run_all_workloads(quick=quick)
    results['mode'] = 'diana'
    results['description'] = 'DIANA Architecture — SYNAPSE Intelligence Active'
    results['warmup_seconds'] = warmup

    # Capture final DIANA state
    results['diana_final_stats'] = read_diana_stats()

    # Stop trainer
    stop_diana_trainer(trainer_proc)

    # Save results
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath = os.path.join(RESULTS_DIR, f'diana_{timestamp}.json')
    with open(filepath, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved: {filepath}")

    return results


def run_full_comparison(quick: bool = False) -> tuple:
    """Run both baseline and DIANA, then generate comparison."""
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  DIANA-OS — Full Performance Comparison              ║")
    print("║                                                      ║")
    print("║  Standard Linux Kernel  vs  DIANA Architecture       ║")
    print("║  (Von Neumann paradigm) vs  (Autonomous Components)  ║")
    print("║                                                      ║")
    print("║  All measurements use REAL system data:              ║")
    print("║  • /proc/self/stat (page faults, CPU ticks)          ║")
    print("║  • /proc/vmstat (cache, swap, paging)                ║")
    print("║  • time.perf_counter_ns() (nanosecond wall clock)    ║")
    print("║  • /proc/diana/stats (SYNAPSE intelligence)          ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print("")

    mode = 'quick' if quick else 'full'
    est_time = '~3 min' if quick else '~10 min'
    print(f"  Mode: {mode} | Estimated time: {est_time}")
    print("")

    # Phase 1: Baseline
    baseline = run_baseline(quick=quick)

    # Phase 2: DIANA
    diana = run_diana(quick=quick)

    # Phase 3: Generate comparison report
    print("")
    print("═══════════════════════════════════════════════════════")
    print("  Generating Comparison Report...")
    print("═══════════════════════════════════════════════════════")

    report = BenchmarkReport(baseline, diana)
    report.print_comparison()

    # Save full report
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = os.path.join(RESULTS_DIR, f'comparison_{timestamp}.json')
    report.save_json(report_path)
    print(f"\n  Full report saved: {report_path}")

    return baseline, diana


# Need this for type hints
from typing import Tuple


# ════════════════════════════════════════════════════════════════
# CLI Entry Point
# ════════════════════════════════════════════════════════════════

def main():
    detect_paths()

    args = sys.argv[1:]
    quick = '--quick' in args
    args = [a for a in args if a != '--quick']

    if '--baseline-only' in args:
        run_baseline(quick=quick)
    elif '--diana-only' in args:
        run_diana(quick=quick)
    elif '--compare' in args:
        idx = args.index('--compare')
        if idx + 2 < len(args):
            from benchmarks.compare_results import compare_files
            compare_files(args[idx + 1], args[idx + 2])
        else:
            print("Usage: --compare BASELINE_FILE DIANA_FILE")
    else:
        run_full_comparison(quick=quick)


if __name__ == '__main__':
    main()
