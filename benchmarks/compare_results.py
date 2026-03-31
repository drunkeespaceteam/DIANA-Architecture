#!/usr/bin/env python3
"""
DIANA-OS — Result Comparison Tool

Load two result files (baseline + DIANA) and produce a comparison.

Usage:
  python3 benchmarks/compare_results.py baseline.json diana.json
  python3 benchmarks/compare_results.py --latest

Author: Sahidh — DIANA Architecture
"""

import os
import sys
import json
import glob
from pathlib import Path
from typing import Dict, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from benchmarks.report_generator import BenchmarkReport


RESULTS_DIR = '/tmp/diana_benchmark/results'


def find_latest_results() -> Tuple[str, str]:
    """Find the most recent baseline and DIANA result files."""
    baseline_files = sorted(glob.glob(os.path.join(RESULTS_DIR, 'baseline_*.json')))
    diana_files = sorted(glob.glob(os.path.join(RESULTS_DIR, 'diana_*.json')))

    if not baseline_files:
        print("No baseline results found!")
        print(f"  Run: python3 benchmarks/benchmark_suite.py --baseline-only")
        sys.exit(1)

    if not diana_files:
        print("No DIANA results found!")
        print(f"  Run: python3 benchmarks/benchmark_suite.py --diana-only")
        sys.exit(1)

    return baseline_files[-1], diana_files[-1]


def compare_files(baseline_path: str, diana_path: str):
    """Load two result files and generate comparison."""
    print(f"Loading baseline: {baseline_path}")
    with open(baseline_path, 'r') as f:
        baseline = json.load(f)

    print(f"Loading DIANA:    {diana_path}")
    with open(diana_path, 'r') as f:
        diana = json.load(f)

    report = BenchmarkReport(baseline, diana)
    report.print_comparison()

    # Save comparison
    os.makedirs(RESULTS_DIR, exist_ok=True)
    report_path = os.path.join(RESULTS_DIR, 'latest_comparison.json')
    report.save_json(report_path)

    csv_path = os.path.join(RESULTS_DIR, 'latest_comparison.csv')
    report.generate_csv(csv_path)

    print(f"\n  JSON report: {report_path}")
    print(f"  CSV report:  {csv_path}")


def list_results():
    """List all available result files."""
    print(f"\n  Results directory: {RESULTS_DIR}\n")

    for pattern, label in [('baseline_*.json', 'Baseline'),
                           ('diana_*.json', 'DIANA'),
                           ('comparison_*.json', 'Comparison')]:
        files = sorted(glob.glob(os.path.join(RESULTS_DIR, pattern)))
        if files:
            print(f"  {label} ({len(files)} files):")
            for f in files[-5:]:  # Show last 5
                size = os.path.getsize(f)
                print(f"    {os.path.basename(f):40s}  ({size:,} bytes)")
            print("")


def deep_compare(baseline: Dict, diana: Dict) -> Dict:
    """
    Deep comparison extracting system-level metrics from /proc data.
    Returns a summary of system-level differences.
    """
    summary = {
        'total_page_faults': {'baseline': 0, 'diana': 0},
        'total_ctx_switches': {'baseline': 0, 'diana': 0},
        'total_user_time': {'baseline': 0, 'diana': 0},
        'total_kernel_time': {'baseline': 0, 'diana': 0},
    }

    for workload_name in baseline.get('workloads', {}):
        for mode_name, data in [('baseline', baseline), ('diana', diana)]:
            workload = data.get('workloads', {}).get(workload_name, {})
            metrics = workload.get('metrics', {})

            summary['total_page_faults'][mode_name] += \
                metrics.get('delta_minor_faults', 0) + \
                metrics.get('delta_major_faults', 0)
            summary['total_ctx_switches'][mode_name] += \
                metrics.get('delta_voluntary_ctx_switches', 0) + \
                metrics.get('delta_involuntary_ctx_switches', 0)
            summary['total_user_time'][mode_name] += \
                metrics.get('delta_user_time', 0)
            summary['total_kernel_time'][mode_name] += \
                metrics.get('delta_system_time', 0)

    return summary


def main():
    args = sys.argv[1:]

    if '--list' in args:
        list_results()
        return

    if '--latest' in args:
        baseline_path, diana_path = find_latest_results()
        compare_files(baseline_path, diana_path)
        return

    if len(args) >= 2:
        compare_files(args[0], args[1])
        return

    # Default: show latest or help
    try:
        baseline_path, diana_path = find_latest_results()
        compare_files(baseline_path, diana_path)
    except SystemExit:
        print("\nUsage:")
        print("  python3 benchmarks/compare_results.py BASELINE.json DIANA.json")
        print("  python3 benchmarks/compare_results.py --latest")
        print("  python3 benchmarks/compare_results.py --list")


if __name__ == '__main__':
    main()
