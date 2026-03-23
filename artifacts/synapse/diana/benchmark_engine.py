"""
DIANA Phase 3 — Benchmark simulation engine.

Runs the same BenchmarkTask through two architectures and returns
structured BenchmarkResult objects ready for display comparison.

TRADITIONAL MODEL
─────────────────
Every step is serialised through the CPU:
  1. Component → CPU: "permission to do X"  (cpu_overhead_ms ÷ 2)
  2. CPU → Component: "granted"             (cpu_overhead_ms ÷ 2)
  3. Component does work                    (step.duration_ms)
  4. Component → CPU: "done" interrupt      (counted in interrupts)

Total time = Σ(step.duration_ms) + N_steps × cpu_overhead_ms
CPU interrupts = N_steps (one permission request per step)

Each component's waiting time = total_time - its_own_work_time
because it idles while every other component negotiates with the CPU.

DIANA MODEL
───────────
Each component runs its own steps sequentially (a component can't
split itself), but ALL components run in parallel with each other.
There is no CPU permission overhead — components talk P2P directly.

Total time = max(component_queue_lengths) + diana_p2p_ms
CPU interrupts = 0
Each component's waiting time = 0 (starts immediately, no permission)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal

from .benchmark_tasks import BenchmarkTask, WorkStep


Architecture = Literal["traditional", "diana"]


@dataclass
class StepRecord:
    """Timing record for a single step in the simulation."""
    component: str
    action: str
    start_ms: float
    end_ms: float
    overhead_ms: float      # CPU permission cost (Traditional only)
    is_waiting: bool = False


@dataclass
class ComponentMetrics:
    name: str
    work_ms: float      # time actually doing useful work
    wait_ms: float      # time blocked waiting for CPU permission
    steps: int


@dataclass
class BenchmarkResult:
    task_name: str
    architecture: Architecture
    total_time_ms: float
    cpu_interrupts: int
    step_records: list[StepRecord]
    component_metrics: dict[str, ComponentMetrics]

    @property
    def work_efficiency(self) -> float:
        """Fraction of total time spent doing real work (not waiting)."""
        total_work = sum(m.work_ms for m in self.component_metrics.values())
        total_possible = self.total_time_ms * len(self.component_metrics)
        return total_work / total_possible if total_possible else 0.0


# ──────────────────────────────────────────────────────────────────────
# Traditional simulator
# ──────────────────────────────────────────────────────────────────────

def simulate_traditional(task: BenchmarkTask) -> BenchmarkResult:
    clock = 0.0
    records: list[StepRecord] = []
    component_work: dict[str, float] = defaultdict(float)
    components = sorted({s.component for s in task.steps})

    for step in task.steps:
        overhead = task.cpu_overhead_ms
        step_start = clock + overhead          # waits for CPU permission first
        step_end   = step_start + step.duration_ms

        # CPU permission wait phase
        records.append(StepRecord(
            component=step.component,
            action=f"[CPU permission] → {step.action}",
            start_ms=clock,
            end_ms=step_start,
            overhead_ms=overhead,
            is_waiting=True,
        ))
        # Actual work phase
        records.append(StepRecord(
            component=step.component,
            action=step.action,
            start_ms=step_start,
            end_ms=step_end,
            overhead_ms=0.0,
        ))

        component_work[step.component] += step.duration_ms
        clock = step_end

    total_time = clock
    cpu_interrupts = len(task.steps)   # one permission request per step

    component_metrics = {
        comp: ComponentMetrics(
            name=comp,
            work_ms=component_work[comp],
            wait_ms=total_time - component_work[comp],
            steps=sum(1 for s in task.steps if s.component == comp),
        )
        for comp in components
    }

    return BenchmarkResult(
        task_name=task.name,
        architecture="traditional",
        total_time_ms=total_time,
        cpu_interrupts=cpu_interrupts,
        step_records=records,
        component_metrics=component_metrics,
    )


# ──────────────────────────────────────────────────────────────────────
# DIANA simulator
# ──────────────────────────────────────────────────────────────────────

def simulate_diana(task: BenchmarkTask) -> BenchmarkResult:
    # Group steps by component; each component runs its own queue in order
    component_steps: dict[str, list[WorkStep]] = defaultdict(list)
    for step in task.steps:
        component_steps[step.component].append(step)

    components = sorted(component_steps)

    # Compute each component's sequential run time (no CPU overhead)
    component_queue: dict[str, float] = {
        comp: sum(s.duration_ms for s in steps)
        for comp, steps in component_steps.items()
    }

    # All components start at t=0 (no CPU permission needed)
    # P2P sync handshake paid once at the start
    p2p_start = task.diana_p2p_ms
    records: list[StepRecord] = []

    for comp, steps in sorted(component_steps.items()):
        clock = p2p_start  # component starts after P2P handshake
        for step in steps:
            records.append(StepRecord(
                component=comp,
                action=step.action,
                start_ms=clock,
                end_ms=clock + step.duration_ms,
                overhead_ms=0.0,
            ))
            clock += step.duration_ms

    # Total DIANA time: slowest component finishes last
    total_time = max(component_queue.values()) + task.diana_p2p_ms

    component_metrics = {
        comp: ComponentMetrics(
            name=comp,
            work_ms=queue_ms,
            wait_ms=0.0,   # no waiting in DIANA — starts immediately
            steps=len(component_steps[comp]),
        )
        for comp, queue_ms in component_queue.items()
    }

    return BenchmarkResult(
        task_name=task.name,
        architecture="diana",
        total_time_ms=total_time,
        cpu_interrupts=0,
        step_records=records,
        component_metrics=component_metrics,
    )


# ──────────────────────────────────────────────────────────────────────
# Comparison report
# ──────────────────────────────────────────────────────────────────────

@dataclass
class TaskComparison:
    task: BenchmarkTask
    traditional: BenchmarkResult
    diana: BenchmarkResult

    @property
    def speedup(self) -> float:
        if self.diana.total_time_ms == 0:
            return float("inf")
        return self.traditional.total_time_ms / self.diana.total_time_ms

    @property
    def interrupt_reduction_pct(self) -> float:
        if self.traditional.cpu_interrupts == 0:
            return 0.0
        return 100.0

    @property
    def time_saved_ms(self) -> float:
        return self.traditional.total_time_ms - self.diana.total_time_ms


def run_benchmark(task: BenchmarkTask) -> TaskComparison:
    return TaskComparison(
        task=task,
        traditional=simulate_traditional(task),
        diana=simulate_diana(task),
    )
