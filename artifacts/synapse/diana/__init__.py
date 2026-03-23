"""
DIANA Architecture — Phase 2
Distributed Intelligence Architecture for Networked Autonomy

Three independent SynapseChip instances (RAM, GPU, SSD) communicate
peer-to-peer, with a passive CPU Reporter that only receives status updates.
"""

from .chip_node import ChipNode, Message
from .cpu_reporter import CPUReporter
from .benchmark import run_benchmarks

__all__ = ["ChipNode", "Message", "CPUReporter", "run_benchmarks"]
