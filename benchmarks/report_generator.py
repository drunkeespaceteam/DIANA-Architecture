#!/usr/bin/env python3
"""
DIANA-OS — Benchmark Report Generator

Generates visual comparison reports between Standard Linux and DIANA.
Outputs: ASCII terminal charts, JSON data, and optionally matplotlib plots.

Author: Sahidh — DIANA Architecture
"""

import os
import sys
import json
from typing import Dict, List, Tuple, Optional
from datetime import datetime


# ════════════════════════════════════════════════════════════════
# ASCII Chart Rendering
# ════════════════════════════════════════════════════════════════

def ascii_bar(label: str, value: float, max_value: float,
              width: int = 40, color: str = '') -> str:
    """Render a single ASCII bar."""
    if max_value <= 0:
        filled = 0
    else:
        filled = int((value / max_value) * width)
    filled = min(filled, width)
    bar = '█' * filled + '░' * (width - filled)

    reset = '\033[0m' if color else ''
    return f"  {label:30s} {color}{bar}{reset} {value:>12.2f}"


def ascii_comparison_bar(label: str, baseline_val: float, diana_val: float,
                         unit: str = 'ns', higher_is_better: bool = False) -> str:
    """Render side-by-side comparison bars."""
    max_val = max(baseline_val, diana_val, 1)

    b_width = int((baseline_val / max_val) * 30)
    d_width = int((diana_val / max_val) * 30)
    b_width = min(b_width, 30)
    d_width = min(d_width, 30)

    b_bar = '█' * b_width + '░' * (30 - b_width)
    d_bar = '█' * d_width + '░' * (30 - d_width)

    # Calculate change
    if baseline_val > 0:
        if higher_is_better:
            change = ((diana_val - baseline_val) / baseline_val) * 100
        else:
            change = ((baseline_val - diana_val) / baseline_val) * 100
    else:
        change = 0

    if change > 0:
        change_str = f'\033[0;32m+{change:.1f}%\033[0m'  # Green
        indicator = '✓'
    elif change < 0:
        change_str = f'\033[0;31m{change:.1f}%\033[0m'  # Red
        indicator = '✗'
    else:
        change_str = f'{change:.1f}%'
        indicator = '='

    lines = [
        f"  {label}:",
        f"    Baseline │ {b_bar} │ {baseline_val:>12.2f} {unit}",
        f"    DIANA    │ {d_bar} │ {diana_val:>12.2f} {unit}  {indicator} {change_str}",
    ]
    return '\n'.join(lines)


# ════════════════════════════════════════════════════════════════
# Report Generator
# ════════════════════════════════════════════════════════════════

class BenchmarkReport:
    """Generates comprehensive comparison reports."""

    def __init__(self, baseline: Dict, diana: Dict):
        self.baseline = baseline
        self.diana = diana
        self.comparisons = self._compute_comparisons()

    def _safe_get(self, results: Dict, workload_name: str,
                  metric: str, default=0) -> float:
        """Safely extract a metric from results."""
        workloads = results.get('workloads', {})
        workload = workloads.get(workload_name, {})
        value = workload.get(metric, default)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _compute_comparisons(self) -> List[Dict]:
        """Compute all metric comparisons between baseline and DIANA."""
        comparisons = []

        # ── Memory benchmarks ──
        memory_metrics = [
            ('Memory: Browser Pattern', 'avg_alloc_ns', 'ns', False,
             'Avg allocation time for browser-like small objects'),
            ('Memory: Browser Pattern', 'p99_alloc_ns', 'ns', False,
             'P99 allocation latency (worst case)'),
            ('Memory: Build Pattern', 'avg_alloc_ns', 'ns', False,
             'Avg allocation time for large build buffers'),
            ('Memory: Repeating Pattern', 'avg_alloc_ns', 'ns', False,
             'Avg allocation time with predictable pattern'),
            ('Memory: Repeating Pattern', 'learning_speedup', 'x', True,
             'Speed improvement from pattern recognition'),
        ]

        # ── File I/O benchmarks ──
        fileio_metrics = [
            ('File I/O: Sequential Read', 'avg_read_ns', 'ns', False,
             'Avg time for sequential 10MB file read'),
            ('File I/O: Sequential Read', 'throughput_mbps', 'MB/s', True,
             'Sequential read throughput'),
            ('File I/O: Random Read', 'avg_read_ns', 'ns', False,
             'Avg time for random 4KB read'),
            ('File I/O: Random Read', 'iops', 'IOPS', True,
             'Random read I/O operations per second'),
            ('File I/O: Many Small Files', 'files_per_second', 'files/s', True,
             'Small file scan throughput'),
            ('File I/O: Repeating Pattern', 'learning_speedup', 'x', True,
             'File access pattern learning effect'),
        ]

        # ── Context switch benchmarks ──
        context_metrics = [
            ('Context: Fork+Exec', 'avg_fork_ns', 'ns', False,
             'Avg fork+exec time'),
            ('Context: Fork+Exec', 'forks_per_second', 'forks/s', True,
             'Process creation rate'),
            ('Context: Pipe Throughput', 'avg_roundtrip_ns', 'ns', False,
             'Avg pipe write+read roundtrip'),
            ('Context: Pipe Throughput', 'throughput_msgs_per_sec', 'msg/s', True,
             'Pipe message throughput'),
            ('Context: Multiprocess', 'tasks_per_second', 'tasks/s', True,
             'Multi-worker task throughput'),
        ]

        # ── Cache benchmarks ──
        cache_metrics = [
            ('Cache: Sequential', 'avg_access_ns', 'ns', False,
             'Avg sequential array access time'),
            ('Cache: Sequential', 'bandwidth_gbps', 'GB/s', True,
             'Sequential memory bandwidth'),
            ('Cache: Random', 'avg_access_ns', 'ns', False,
             'Avg random array access time'),
            ('Cache: Random', 'accesses_per_second', 'acc/s', True,
             'Random access throughput'),
            ('Cache: Hot/Cold', 'avg_hot_access_ns', 'ns', False,
             'Avg hot region access time'),
            ('Cache: Hot/Cold', 'hot_cold_ratio', 'ratio', True,
             'Hot/cold access time ratio'),
        ]

        all_metrics = (
            [('MEMORY', m) for m in memory_metrics] +
            [('FILE I/O', m) for m in fileio_metrics] +
            [('CONTEXT SWITCH', m) for m in context_metrics] +
            [('CACHE', m) for m in cache_metrics]
        )

        for category, (workload, metric, unit, higher_better, desc) in all_metrics:
            baseline_val = self._safe_get(self.baseline, workload, metric)
            diana_val = self._safe_get(self.diana, workload, metric)

            if baseline_val > 0:
                if higher_better:
                    change_pct = ((diana_val - baseline_val) / baseline_val) * 100
                else:
                    change_pct = ((baseline_val - diana_val) / baseline_val) * 100
            else:
                change_pct = 0

            comparisons.append({
                'category': category,
                'workload': workload,
                'metric': metric,
                'unit': unit,
                'higher_is_better': higher_better,
                'description': desc,
                'baseline': baseline_val,
                'diana': diana_val,
                'change_pct': change_pct,
                'improved': change_pct > 0,
            })

        return comparisons

    def _get_system_metrics_comparison(self) -> Dict:
        """Extract system-level metrics from both runs."""
        result = {}

        for comp in self.comparisons:
            workload = comp['workload']
            for mode in ['baseline', 'diana']:
                data = self.baseline if mode == 'baseline' else self.diana
                workload_data = data.get('workloads', {}).get(workload, {})
                metrics = workload_data.get('metrics', {})

                key = f'{mode}_{workload}'
                result[key] = {
                    'page_faults': metrics.get('delta_minor_faults', 0) + \
                                   metrics.get('delta_major_faults', 0),
                    'ctx_switches': metrics.get('delta_voluntary_ctx_switches', 0) + \
                                    metrics.get('delta_involuntary_ctx_switches', 0),
                    'user_time': metrics.get('delta_user_time', 0),
                    'kernel_time': metrics.get('delta_system_time', 0),
                }

        return result

    def print_comparison(self):
        """Print the full comparison report to terminal."""
        print("")
        print("╔═══════════════════════════════════════════════════════════════════════════╗")
        print("║                                                                         ║")
        print("║   ██████╗ ██╗ █████╗ ███╗   ██╗ █████╗        ██████╗ ███████╗          ║")
        print("║   ██╔══██╗██║██╔══██╗████╗  ██║██╔══██╗      ██╔═══██╗██╔════╝          ║")
        print("║   ██║  ██║██║███████║██╔██╗ ██║███████║█████╗██║   ██║███████╗           ║")
        print("║   ██║  ██║██║██╔══██║██║╚██╗██║██╔══██║╚════╝██║   ██║╚════██║           ║")
        print("║   ██████╔╝██║██║  ██║██║ ╚████║██║  ██║      ╚██████╔╝███████║           ║")
        print("║   ╚═════╝ ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝       ╚═════╝ ╚══════╝           ║")
        print("║                                                                         ║")
        print("║       PERFORMANCE BENCHMARK — REAL DATA COMPARISON                      ║")
        print("║       Standard Linux (Von Neumann) vs DIANA Architecture                ║")
        print("╚═══════════════════════════════════════════════════════════════════════════╝")
        print("")

        # System info
        print(f"  Date:     {self.baseline.get('timestamp', 'unknown')}")
        print(f"  Kernel:   {self.baseline.get('kernel', 'unknown')}")
        diana_loaded = self.diana.get('diana_loaded', False)
        diana_status = '\033[0;32mACTIVE\033[0m' if diana_loaded else '\033[0;31mNOT LOADED\033[0m'
        print(f"  DIANA:    {diana_status}")
        print("")

        # Print each category
        current_category = None
        improvements = 0
        regressions = 0
        neutral = 0

        for comp in self.comparisons:
            if comp['category'] != current_category:
                current_category = comp['category']
                print(f"\n  ┌─────────────────────────────────────────────────────────────┐")
                print(f"  │  {current_category:^57s}  │")
                print(f"  └─────────────────────────────────────────────────────────────┘")
                print("")

            result = ascii_comparison_bar(
                comp['description'],
                comp['baseline'],
                comp['diana'],
                comp['unit'],
                comp['higher_is_better']
            )
            print(result)
            print("")

            if comp['change_pct'] > 1:
                improvements += 1
            elif comp['change_pct'] < -1:
                regressions += 1
            else:
                neutral += 1

        # Summary
        total = len(self.comparisons)
        avg_improvement = sum(c['change_pct'] for c in self.comparisons) / total \
            if total > 0 else 0

        print("")
        print("  ╔═══════════════════════════════════════════════════════╗")
        print("  ║                   OVERALL VERDICT                    ║")
        print("  ╠═══════════════════════════════════════════════════════╣")
        print(f"  ║  Total metrics compared:  {total:>3d}                        ║")

        if improvements > 0:
            print(f"  ║  \033[0;32mImprovements:             {improvements:>3d}\033[0m                        ║")
        else:
            print(f"  ║  Improvements:             {improvements:>3d}                        ║")

        if regressions > 0:
            print(f"  ║  \033[0;31mRegressions:              {regressions:>3d}\033[0m                        ║")
        else:
            print(f"  ║  Regressions:              {regressions:>3d}                        ║")

        print(f"  ║  Neutral:                  {neutral:>3d}                        ║")

        if avg_improvement > 0:
            color = '\033[0;32m'
        elif avg_improvement < 0:
            color = '\033[0;31m'
        else:
            color = ''
        reset = '\033[0m' if color else ''

        print(f"  ║                                                      ║")
        print(f"  ║  Average change: {color}{avg_improvement:>+.2f}%{reset}                            ║")
        print(f"  ║                                                      ║")

        if avg_improvement > 5:
            print(f"  ║  \033[0;32m★ DIANA WINS — Autonomous intelligence is faster\033[0m   ║")
        elif avg_improvement > 0:
            print(f"  ║  \033[0;32m~ DIANA shows marginal improvement\033[0m                 ║")
        elif avg_improvement > -5:
            print(f"  ║  ~ Results are within noise margin                 ║")
        else:
            print(f"  ║  \033[0;31m★ BASELINE WINS — Standard kernel is faster\033[0m       ║")

        print(f"  ╚═══════════════════════════════════════════════════════╝")
        print("")

        # DIANA-specific stats
        diana_stats = self.diana.get('diana_final_stats', {})
        if diana_stats.get('diana_loaded'):
            print("  ┌───────────────────────────────────────────┐")
            print("  │  DIANA SYNAPSE Status After Benchmark     │")
            print("  └───────────────────────────────────────────┘")
            for key in ['total_messages', 'commands_issued',
                        'status_updates_received']:
                if key in diana_stats:
                    val = diana_stats[key]
                    highlight = '\033[0;32m' if key == 'commands_issued' and str(val) == '0' else ''
                    reset = '\033[0m' if highlight else ''
                    print(f"    {key:35s} {highlight}{val}{reset}")

            # CPU commands must ALWAYS be 0 — core DIANA invariant
            cpu_cmds = diana_stats.get('commands_issued', '?')
            if str(cpu_cmds) == '0':
                print("")
                print("    \033[0;32m✓ CPU OBSERVER: 0 commands issued (DIANA invariant holds)\033[0m")
            else:
                print("")
                print(f"    \033[0;31m✗ CPU OBSERVER: {cpu_cmds} commands! INVARIANT VIOLATED!\033[0m")

        print("")

    def save_json(self, filepath: str):
        """Save complete comparison results as JSON."""
        report = {
            'generated_at': datetime.now().isoformat(),
            'baseline': self.baseline,
            'diana': self.diana,
            'comparisons': self.comparisons,
            'summary': {
                'total_metrics': len(self.comparisons),
                'improvements': sum(1 for c in self.comparisons if c['change_pct'] > 1),
                'regressions': sum(1 for c in self.comparisons if c['change_pct'] < -1),
                'neutral': sum(1 for c in self.comparisons if -1 <= c['change_pct'] <= 1),
                'avg_change_pct': sum(c['change_pct'] for c in self.comparisons) / \
                    len(self.comparisons) if self.comparisons else 0,
            }
        }

        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)

    def generate_csv(self, filepath: str):
        """Save comparison as CSV for spreadsheet analysis."""
        with open(filepath, 'w') as f:
            f.write('Category,Workload,Metric,Unit,Baseline,DIANA,Change%,Improved\n')
            for c in self.comparisons:
                f.write(f"{c['category']},{c['workload']},{c['metric']},"
                        f"{c['unit']},{c['baseline']:.6f},{c['diana']:.6f},"
                        f"{c['change_pct']:.2f},{c['improved']}\n")


if __name__ == '__main__':
    # Test with dummy data
    print("Report generator loaded. Use benchmark_suite.py to generate reports.")
