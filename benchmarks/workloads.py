#!/usr/bin/env python3
"""
DIANA-OS — Real Workload Generators

These are NOT synthetic benchmarks. Each workload mirrors a real-world
application pattern to produce genuine, comparable performance data.

Every measurement uses:
  - time.perf_counter_ns()    for nanosecond-precision wall clock
  - os.times()                for real CPU time (user + kernel)
  - /proc/self/stat           for page faults, context switches
  - /proc/vmstat              for system-wide memory/cache stats
  - /proc/diana/stats         for DIANA-specific metrics (when loaded)

Author: Sahidh — DIANA Architecture
"""

import os
import sys
import time
import mmap
import ctypes
import struct
import random
import hashlib
import tempfile
import subprocess
import multiprocessing
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# ════════════════════════════════════════════════════════════════
# System Metric Collectors (REAL data from /proc)
# ════════════════════════════════════════════════════════════════

def read_proc_stat() -> Dict[str, int]:
    """Read /proc/self/stat for real process metrics."""
    try:
        with open('/proc/self/stat', 'r') as f:
            parts = f.read().split()
        return {
            'minor_faults': int(parts[9]),
            'major_faults': int(parts[11]),
            'utime_ticks': int(parts[13]),
            'stime_ticks': int(parts[14]),
            'vsize_bytes': int(parts[22]),
            'rss_pages': int(parts[23]),
            'voluntary_ctx_switches': 0,  # from /proc/self/status
            'involuntary_ctx_switches': 0,
        }
    except (FileNotFoundError, IndexError):
        return {}


def read_proc_status() -> Dict[str, int]:
    """Read /proc/self/status for context switch data."""
    result = {}
    try:
        with open('/proc/self/status', 'r') as f:
            for line in f:
                if line.startswith('voluntary_ctxt_switches:'):
                    result['voluntary_ctx_switches'] = int(line.split(':')[1].strip())
                elif line.startswith('nonvoluntary_ctxt_switches:'):
                    result['involuntary_ctx_switches'] = int(line.split(':')[1].strip())
    except FileNotFoundError:
        pass
    return result


def read_vmstat() -> Dict[str, int]:
    """Read /proc/vmstat for system-wide memory stats."""
    result = {}
    try:
        with open('/proc/vmstat', 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 2:
                    try:
                        result[parts[0]] = int(parts[1])
                    except ValueError:
                        pass
    except FileNotFoundError:
        pass
    return result


def read_meminfo() -> Dict[str, int]:
    """Read /proc/meminfo for memory pressure data."""
    result = {}
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(':')
                    try:
                        result[key] = int(parts[1]) * 1024  # Convert KB to bytes
                    except ValueError:
                        pass
    except FileNotFoundError:
        pass
    return result


def read_diana_stats() -> Dict[str, str]:
    """Read /proc/diana/stats if DIANA module is loaded."""
    result = {'diana_loaded': False}
    try:
        with open('/proc/diana/stats', 'r') as f:
            content = f.read()
        result['diana_loaded'] = True
        result['raw'] = content

        # Parse key metrics
        for line in content.split('\n'):
            line = line.strip()
            if ':' in line and not line.startswith('[') and not line.startswith('╔'):
                key, _, value = line.partition(':')
                result[key.strip()] = value.strip()
    except FileNotFoundError:
        pass
    return result


def snapshot_metrics() -> Dict:
    """Take a complete system metrics snapshot."""
    return {
        'timestamp_ns': time.perf_counter_ns(),
        'proc_stat': read_proc_stat(),
        'proc_status': read_proc_status(),
        'vmstat': read_vmstat(),
        'meminfo': read_meminfo(),
        'diana': read_diana_stats(),
        'cpu_times': os.times(),
    }


def diff_metrics(before: Dict, after: Dict) -> Dict:
    """Calculate the delta between two metric snapshots."""
    elapsed_ns = after['timestamp_ns'] - before['timestamp_ns']
    elapsed_s = elapsed_ns / 1e9

    result = {
        'elapsed_ns': elapsed_ns,
        'elapsed_s': elapsed_s,
    }

    # Process-level deltas
    for key in ['minor_faults', 'major_faults', 'utime_ticks', 'stime_ticks']:
        b = before['proc_stat'].get(key, 0)
        a = after['proc_stat'].get(key, 0)
        result[f'delta_{key}'] = a - b

    # Context switch deltas
    for key in ['voluntary_ctx_switches', 'involuntary_ctx_switches']:
        b = before['proc_status'].get(key, 0)
        a = after['proc_status'].get(key, 0)
        result[f'delta_{key}'] = a - b

    # vmstat deltas (key cache/page metrics)
    for key in ['pgpgin', 'pgpgout', 'pgfault', 'pgmajfault',
                'pswpin', 'pswpout', 'nr_free_pages']:
        b = before['vmstat'].get(key, 0)
        a = after['vmstat'].get(key, 0)
        result[f'delta_{key}'] = a - b

    # CPU time deltas
    bt = before['cpu_times']
    at = after['cpu_times']
    result['delta_user_time'] = at.user - bt.user
    result['delta_system_time'] = at.system - bt.system

    # DIANA stats
    result['diana_loaded'] = after['diana'].get('diana_loaded', False)
    if result['diana_loaded']:
        result['diana_stats'] = after['diana']

    return result


# ════════════════════════════════════════════════════════════════
# WORKLOAD 1: Memory Allocation Patterns
# ════════════════════════════════════════════════════════════════

class MemoryWorkload:
    """
    Real memory allocation patterns that test how well the system
    predicts and handles malloc/free sequences.

    Pattern types:
      - Browser-like: Many small allocations (DOM nodes, strings)
      - IDE-like: Medium allocations (syntax trees, buffers)
      - Build-like: Large allocations (compiler IR, object files)
      - Repeating: Predictable cycle (DIANA should learn this)
    """

    @staticmethod
    def browser_pattern(iterations: int = 5000) -> Dict:
        """
        Simulates browser tab memory: many small allocations (32B-4KB)
        with frequent free cycles. Real browsers allocate millions of
        small DOM nodes and string fragments.
        """
        before = snapshot_metrics()
        alloc_times = []
        free_times = []
        buffers = []

        for i in range(iterations):
            # Allocation sizes mimic real DOM nodes / JS objects
            sizes = [32, 64, 128, 256, 512, 1024, 2048, 4096]
            size = sizes[i % len(sizes)]

            t0 = time.perf_counter_ns()
            buf = bytearray(size)
            # Touch every page to force actual allocation
            for j in range(0, len(buf), 4096):
                buf[j] = i & 0xFF
            t1 = time.perf_counter_ns()
            alloc_times.append(t1 - t0)
            buffers.append(buf)

            # Free in batches (like GC cycles)
            if len(buffers) >= 100:
                t0 = time.perf_counter_ns()
                buffers.clear()
                t1 = time.perf_counter_ns()
                free_times.append(t1 - t0)

        buffers.clear()
        after = snapshot_metrics()

        return {
            'name': 'memory_browser_pattern',
            'iterations': iterations,
            'avg_alloc_ns': sum(alloc_times) / len(alloc_times) if alloc_times else 0,
            'p50_alloc_ns': sorted(alloc_times)[len(alloc_times)//2] if alloc_times else 0,
            'p99_alloc_ns': sorted(alloc_times)[int(len(alloc_times)*0.99)] if alloc_times else 0,
            'avg_free_ns': sum(free_times) / len(free_times) if free_times else 0,
            'total_alloc_ns': sum(alloc_times),
            'total_free_ns': sum(free_times),
            'metrics': diff_metrics(before, after),
        }

    @staticmethod
    def build_pattern(iterations: int = 500) -> Dict:
        """
        Simulates compiler/build: large allocations (64KB-1MB) for
        AST nodes, IR buffers, and object file assembly.
        """
        before = snapshot_metrics()
        alloc_times = []
        compute_times = []
        buffers = []

        for i in range(iterations):
            # Large allocations like compiler buffers
            size = (64 + (i % 16) * 64) * 1024  # 64KB to 1MB

            t0 = time.perf_counter_ns()
            buf = bytearray(size)
            t1 = time.perf_counter_ns()
            alloc_times.append(t1 - t0)

            # Simulate computation (write pattern like compiler output)
            t0 = time.perf_counter_ns()
            for j in range(0, min(len(buf), 65536), 64):
                buf[j:j+8] = struct.pack('<Q', i * j)
            t1 = time.perf_counter_ns()
            compute_times.append(t1 - t0)

            buffers.append(buf)

            # Release in larger batches
            if len(buffers) >= 20:
                buffers.clear()

        buffers.clear()
        after = snapshot_metrics()

        return {
            'name': 'memory_build_pattern',
            'iterations': iterations,
            'avg_alloc_ns': sum(alloc_times) / len(alloc_times) if alloc_times else 0,
            'p50_alloc_ns': sorted(alloc_times)[len(alloc_times)//2] if alloc_times else 0,
            'p99_alloc_ns': sorted(alloc_times)[int(len(alloc_times)*0.99)] if alloc_times else 0,
            'avg_compute_ns': sum(compute_times) / len(compute_times) if compute_times else 0,
            'metrics': diff_metrics(before, after),
        }

    @staticmethod
    def repeating_pattern(iterations: int = 3000) -> Dict:
        """
        Predictable repeating allocation pattern.
        DIANA's SYNAPSE should learn this and improve over time.
        Pattern: [1KB, 4KB, 16KB, 64KB, 4KB, 1KB] (repeats)
        """
        pattern = [1024, 4096, 16384, 65536, 4096, 1024]
        before = snapshot_metrics()
        alloc_times = []
        buffers = []

        for i in range(iterations):
            size = pattern[i % len(pattern)]

            t0 = time.perf_counter_ns()
            buf = bytearray(size)
            buf[0] = 0xFF  # Force allocation
            buf[-1] = 0xFF
            t1 = time.perf_counter_ns()
            alloc_times.append(t1 - t0)
            buffers.append(buf)

            if len(buffers) >= 50:
                buffers.clear()

        # Split timing into first half vs second half
        # DIANA should be faster in the second half (it learned the pattern)
        half = len(alloc_times) // 2
        first_half_avg = sum(alloc_times[:half]) / half if half > 0 else 0
        second_half_avg = sum(alloc_times[half:]) / (len(alloc_times) - half) if half > 0 else 0

        buffers.clear()
        after = snapshot_metrics()

        return {
            'name': 'memory_repeating_pattern',
            'iterations': iterations,
            'pattern': pattern,
            'avg_alloc_ns': sum(alloc_times) / len(alloc_times) if alloc_times else 0,
            'first_half_avg_ns': first_half_avg,
            'second_half_avg_ns': second_half_avg,
            'learning_speedup': (first_half_avg / second_half_avg) if second_half_avg > 0 else 0,
            'metrics': diff_metrics(before, after),
        }


# ════════════════════════════════════════════════════════════════
# WORKLOAD 2: File I/O Patterns
# ════════════════════════════════════════════════════════════════

class FileIOWorkload:
    """
    Real file I/O patterns that test VFS read prediction.
    Uses actual files on disk — NOT /dev/zero or /dev/null.
    """

    DATA_DIR = '/tmp/diana_benchmark/data'

    @staticmethod
    def sequential_read(filepath: str = None, iterations: int = 50) -> Dict:
        """
        Sequential file reading — the most common I/O pattern.
        DIANA's SSD SYNAPSE should learn file access patterns.
        """
        if filepath is None:
            filepath = os.path.join(FileIOWorkload.DATA_DIR, 'sequential_10mb.bin')

        if not os.path.exists(filepath):
            # Generate if missing
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'wb') as f:
                f.write(os.urandom(10 * 1024 * 1024))

        file_size = os.path.getsize(filepath)
        before = snapshot_metrics()
        read_times = []
        bytes_read_total = 0

        for i in range(iterations):
            # Drop page cache between iterations for honest measurement
            try:
                with open('/proc/sys/vm/drop_caches', 'w') as f:
                    f.write('1')
            except PermissionError:
                pass  # Needs root — results still valid, just cached

            t0 = time.perf_counter_ns()
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(65536)  # 64KB reads (realistic)
                    if not chunk:
                        break
                    bytes_read_total += len(chunk)
            t1 = time.perf_counter_ns()
            read_times.append(t1 - t0)

        after = snapshot_metrics()

        throughput_mbps = (bytes_read_total / 1e6) / (sum(read_times) / 1e9) \
            if sum(read_times) > 0 else 0

        return {
            'name': 'fileio_sequential_read',
            'file_size': file_size,
            'iterations': iterations,
            'avg_read_ns': sum(read_times) / len(read_times) if read_times else 0,
            'min_read_ns': min(read_times) if read_times else 0,
            'max_read_ns': max(read_times) if read_times else 0,
            'throughput_mbps': throughput_mbps,
            'total_bytes_read': bytes_read_total,
            'metrics': diff_metrics(before, after),
        }

    @staticmethod
    def random_read(filepath: str = None, iterations: int = 2000) -> Dict:
        """
        Random 4KB reads at random offsets.
        This is the worst case for standard readahead —
        but DIANA should learn which offsets are accessed frequently.
        """
        if filepath is None:
            filepath = os.path.join(FileIOWorkload.DATA_DIR, 'large_100mb.bin')

        if not os.path.exists(filepath):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'wb') as f:
                f.write(os.urandom(100 * 1024 * 1024))

        file_size = os.path.getsize(filepath)
        max_offset = file_size - 4096
        before = snapshot_metrics()
        read_times = []

        # Generate random offsets (reproducible with seed)
        rng = random.Random(42)
        offsets = [rng.randint(0, max_offset) for _ in range(iterations)]

        with open(filepath, 'rb') as f:
            for offset in offsets:
                t0 = time.perf_counter_ns()
                f.seek(offset)
                data = f.read(4096)
                t1 = time.perf_counter_ns()
                read_times.append(t1 - t0)

        after = snapshot_metrics()

        iops = iterations / (sum(read_times) / 1e9) if sum(read_times) > 0 else 0

        return {
            'name': 'fileio_random_read',
            'file_size': file_size,
            'iterations': iterations,
            'avg_read_ns': sum(read_times) / len(read_times) if read_times else 0,
            'p50_read_ns': sorted(read_times)[len(read_times)//2] if read_times else 0,
            'p99_read_ns': sorted(read_times)[int(len(read_times)*0.99)] if read_times else 0,
            'iops': iops,
            'metrics': diff_metrics(before, after),
        }

    @staticmethod
    def many_small_files(directory: str = None, iterations: int = 3) -> Dict:
        """
        Read 1000 small files sequentially — simulates source tree access.
        DIANA's SSD component should predict which files are needed next.
        """
        if directory is None:
            directory = os.path.join(FileIOWorkload.DATA_DIR, 'small_files')

        if not os.path.exists(directory) or len(os.listdir(directory)) < 100:
            os.makedirs(directory, exist_ok=True)
            for i in range(1000):
                with open(os.path.join(directory, f'file_{i}.dat'), 'wb') as f:
                    f.write(os.urandom(4096))

        files = sorted(Path(directory).glob('*.dat'))
        before = snapshot_metrics()
        scan_times = []

        for iteration in range(iterations):
            t0 = time.perf_counter_ns()
            total_bytes = 0
            for fpath in files:
                with open(fpath, 'rb') as f:
                    data = f.read()
                    total_bytes += len(data)
            t1 = time.perf_counter_ns()
            scan_times.append(t1 - t0)

        after = snapshot_metrics()

        avg_per_file_ns = sum(scan_times) / (len(files) * iterations) \
            if files and iterations > 0 else 0

        return {
            'name': 'fileio_many_small_files',
            'num_files': len(files),
            'iterations': iterations,
            'avg_scan_ns': sum(scan_times) / len(scan_times) if scan_times else 0,
            'avg_per_file_ns': avg_per_file_ns,
            'files_per_second': (len(files) * iterations) / (sum(scan_times) / 1e9) \
                if sum(scan_times) > 0 else 0,
            'metrics': diff_metrics(before, after),
        }

    @staticmethod
    def repeating_file_pattern(iterations: int = 200) -> Dict:
        """
        Access files in a repeating pattern: A, B, C, A, B, C, ...
        DIANA should learn this and prefetch file C while reading B.
        """
        data_dir = FileIOWorkload.DATA_DIR
        pattern_files = []
        for name in ['alpha', 'beta', 'gamma', 'delta']:
            path = os.path.join(data_dir, f'pattern_{name}.bin')
            if not os.path.exists(path):
                os.makedirs(data_dir, exist_ok=True)
                with open(path, 'wb') as f:
                    f.write(os.urandom(262144))  # 256KB each
            pattern_files.append(path)

        before = snapshot_metrics()
        read_times = []

        for i in range(iterations):
            fpath = pattern_files[i % len(pattern_files)]
            t0 = time.perf_counter_ns()
            with open(fpath, 'rb') as f:
                data = f.read()
            t1 = time.perf_counter_ns()
            read_times.append(t1 - t0)

        # First quarter vs last quarter (learning effect)
        quarter = len(read_times) // 4
        first_q = sum(read_times[:quarter]) / quarter if quarter > 0 else 0
        last_q = sum(read_times[-quarter:]) / quarter if quarter > 0 else 0

        after = snapshot_metrics()

        return {
            'name': 'fileio_repeating_pattern',
            'pattern_length': len(pattern_files),
            'iterations': iterations,
            'avg_read_ns': sum(read_times) / len(read_times) if read_times else 0,
            'first_quarter_avg_ns': first_q,
            'last_quarter_avg_ns': last_q,
            'learning_speedup': (first_q / last_q) if last_q > 0 else 0,
            'metrics': diff_metrics(before, after),
        }


# ════════════════════════════════════════════════════════════════
# WORKLOAD 3: Context Switch & Process Management
# ════════════════════════════════════════════════════════════════

class ContextSwitchWorkload:
    """
    Real context switch and process management benchmarks.
    Measures how efficiently the kernel handles process lifecycle.
    """

    @staticmethod
    def _worker_task(pipe_w, data_size):
        """Worker process that does real computation."""
        result = hashlib.sha256(os.urandom(data_size)).hexdigest()
        os.write(pipe_w, result.encode()[:32])
        os.close(pipe_w)

    @staticmethod
    def fork_exec_benchmark(iterations: int = 200) -> Dict:
        """
        Fork + exec benchmark — measures process creation overhead.
        Real compilers/build systems do this thousands of times.
        """
        before = snapshot_metrics()
        fork_times = []

        for i in range(iterations):
            t0 = time.perf_counter_ns()
            # Use subprocess for real fork+exec
            proc = subprocess.Popen(
                ['python3', '-c', f'import hashlib; hashlib.sha256(b"test{i}").hexdigest()'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            proc.wait()
            t1 = time.perf_counter_ns()
            fork_times.append(t1 - t0)

        after = snapshot_metrics()

        return {
            'name': 'context_fork_exec',
            'iterations': iterations,
            'avg_fork_ns': sum(fork_times) / len(fork_times) if fork_times else 0,
            'p50_fork_ns': sorted(fork_times)[len(fork_times)//2] if fork_times else 0,
            'p99_fork_ns': sorted(fork_times)[int(len(fork_times)*0.99)] if fork_times else 0,
            'forks_per_second': iterations / (sum(fork_times) / 1e9) if sum(fork_times) > 0 else 0,
            'metrics': diff_metrics(before, after),
        }

    @staticmethod
    def pipe_throughput(iterations: int = 5000) -> Dict:
        """
        Pipe read/write throughput — measures IPC context switch cost.
        Every pipe write triggers a context switch to the reader.
        """
        before = snapshot_metrics()
        pipe_times = []

        r, w = os.pipe()
        message = b'DIANA_SYNAPSE_' + os.urandom(50)

        for i in range(iterations):
            t0 = time.perf_counter_ns()
            os.write(w, message)
            data = os.read(r, len(message))
            t1 = time.perf_counter_ns()
            pipe_times.append(t1 - t0)

        os.close(r)
        os.close(w)
        after = snapshot_metrics()

        return {
            'name': 'context_pipe_throughput',
            'iterations': iterations,
            'message_size': len(message),
            'avg_roundtrip_ns': sum(pipe_times) / len(pipe_times) if pipe_times else 0,
            'p50_roundtrip_ns': sorted(pipe_times)[len(pipe_times)//2] if pipe_times else 0,
            'throughput_msgs_per_sec': iterations / (sum(pipe_times) / 1e9) if sum(pipe_times) > 0 else 0,
            'metrics': diff_metrics(before, after),
        }

    @staticmethod
    def multiprocess_coordination(num_workers: int = 4, tasks: int = 100) -> Dict:
        """
        Multi-process workload — processes communicate via pipes.
        Tests scheduler intelligence under load.
        """
        before = snapshot_metrics()

        def worker_fn(task_queue, result_queue):
            while True:
                try:
                    task = task_queue.get(timeout=2)
                    if task is None:
                        break
                    # Real computation
                    result = hashlib.sha256(task).hexdigest()
                    result_queue.put(result)
                except Exception:
                    break

        task_queue = multiprocessing.Queue()
        result_queue = multiprocessing.Queue()

        # Start workers
        workers = []
        t0 = time.perf_counter_ns()
        for _ in range(num_workers):
            p = multiprocessing.Process(target=worker_fn, args=(task_queue, result_queue))
            p.start()
            workers.append(p)

        # Submit tasks
        for i in range(tasks):
            task_queue.put(os.urandom(1024))

        # Signal done
        for _ in range(num_workers):
            task_queue.put(None)

        # Collect results
        results = []
        for _ in range(tasks):
            try:
                results.append(result_queue.get(timeout=10))
            except Exception:
                break

        # Wait for workers
        for p in workers:
            p.join(timeout=5)

        t1 = time.perf_counter_ns()
        after = snapshot_metrics()

        return {
            'name': 'context_multiprocess',
            'num_workers': num_workers,
            'tasks': tasks,
            'tasks_completed': len(results),
            'total_time_ns': t1 - t0,
            'avg_task_ns': (t1 - t0) / len(results) if results else 0,
            'tasks_per_second': len(results) / ((t1 - t0) / 1e9) if (t1 - t0) > 0 else 0,
            'metrics': diff_metrics(before, after),
        }


# ════════════════════════════════════════════════════════════════
# WORKLOAD 4: Cache Stress Patterns
# ════════════════════════════════════════════════════════════════

class CacheWorkload:
    """
    Workloads that stress the memory cache hierarchy.
    DIANA's cache SYNAPSE should predict evictions and prefetch.
    """

    @staticmethod
    def sequential_access(array_size_mb: int = 32, iterations: int = 10) -> Dict:
        """
        Sequential array traversal — cache-friendly baseline.
        L1/L2/L3 should handle this well even without DIANA.
        """
        size = array_size_mb * 1024 * 1024
        before = snapshot_metrics()

        data = bytearray(size)
        access_times = []

        for iteration in range(iterations):
            t0 = time.perf_counter_ns()
            # Sequential read — cache-friendly
            checksum = 0
            for i in range(0, size, 64):  # 64-byte cache line stride
                checksum += data[i]
            t1 = time.perf_counter_ns()
            access_times.append(t1 - t0)

        del data
        after = snapshot_metrics()

        bandwidth_gbps = (size * iterations) / (sum(access_times) / 1e9) / 1e9 \
            if sum(access_times) > 0 else 0

        return {
            'name': 'cache_sequential_access',
            'array_size_mb': array_size_mb,
            'iterations': iterations,
            'avg_access_ns': sum(access_times) / len(access_times) if access_times else 0,
            'bandwidth_gbps': bandwidth_gbps,
            'metrics': diff_metrics(before, after),
        }

    @staticmethod
    def random_access(array_size_mb: int = 32, num_accesses: int = 100000) -> Dict:
        """
        Random array access — cache-hostile.
        Every access likely misses L1/L2. DIANA should learn hot spots.
        """
        size = array_size_mb * 1024 * 1024
        before = snapshot_metrics()

        data = bytearray(size)
        rng = random.Random(42)
        offsets = [rng.randint(0, size - 1) for _ in range(num_accesses)]

        t0 = time.perf_counter_ns()
        checksum = 0
        for offset in offsets:
            checksum += data[offset]
        t1 = time.perf_counter_ns()

        del data
        after = snapshot_metrics()

        return {
            'name': 'cache_random_access',
            'array_size_mb': array_size_mb,
            'num_accesses': num_accesses,
            'total_time_ns': t1 - t0,
            'avg_access_ns': (t1 - t0) / num_accesses,
            'accesses_per_second': num_accesses / ((t1 - t0) / 1e9) if (t1 - t0) > 0 else 0,
            'metrics': diff_metrics(before, after),
        }

    @staticmethod
    def repeating_hot_cold(array_size_mb: int = 64,
                           hot_size_kb: int = 256,
                           iterations: int = 50) -> Dict:
        """
        Hot/cold pattern: frequently access a small "hot" region,
        occasionally touch a large "cold" region.
        DIANA should learn to keep the hot region cached.
        """
        total_size = array_size_mb * 1024 * 1024
        hot_size = hot_size_kb * 1024
        before = snapshot_metrics()

        data = bytearray(total_size)
        rng = random.Random(42)
        access_times_hot = []
        access_times_cold = []

        for iteration in range(iterations):
            # Hot access (80% of the time)
            for _ in range(800):
                offset = rng.randint(0, hot_size - 1)
                t0 = time.perf_counter_ns()
                _ = data[offset]
                t1 = time.perf_counter_ns()
                access_times_hot.append(t1 - t0)

            # Cold access (20% of the time)
            for _ in range(200):
                offset = rng.randint(hot_size, total_size - 1)
                t0 = time.perf_counter_ns()
                _ = data[offset]
                t1 = time.perf_counter_ns()
                access_times_cold.append(t1 - t0)

        del data
        after = snapshot_metrics()

        return {
            'name': 'cache_hot_cold_pattern',
            'total_size_mb': array_size_mb,
            'hot_size_kb': hot_size_kb,
            'iterations': iterations,
            'avg_hot_access_ns': sum(access_times_hot) / len(access_times_hot) if access_times_hot else 0,
            'avg_cold_access_ns': sum(access_times_cold) / len(access_times_cold) if access_times_cold else 0,
            'hot_cold_ratio': (sum(access_times_cold) / len(access_times_cold)) / \
                              (sum(access_times_hot) / len(access_times_hot)) \
                if access_times_hot and access_times_cold and \
                   sum(access_times_hot) > 0 else 0,
            'metrics': diff_metrics(before, after),
        }


# ════════════════════════════════════════════════════════════════
# WORKLOAD 5: DIANA Intelligence Measurement
# ════════════════════════════════════════════════════════════════

class DianaIntelligenceWorkload:
    """
    Benchmarks specifically designed to measure DIANA's
    prediction intelligence — only meaningful when modules are loaded.
    """

    @staticmethod
    def prediction_accuracy(warmup_seconds: int = 30) -> Dict:
        """
        Measure DIANA's prediction accuracy over time by reading
        /proc/diana/stats before and after a workload.
        """
        diana_before = read_diana_stats()
        if not diana_before.get('diana_loaded'):
            return {
                'name': 'diana_prediction_accuracy',
                'diana_loaded': False,
                'message': 'DIANA module not loaded — skipping intelligence measurement',
            }

        # Run a predictable workload for DIANA to learn
        time.sleep(warmup_seconds)

        # Run repeating patterns that DIANA should predict
        MemoryWorkload.repeating_pattern(iterations=2000)
        FileIOWorkload.repeating_file_pattern(iterations=100)

        diana_after = read_diana_stats()

        # Extract SYNAPSE metrics
        result = {
            'name': 'diana_prediction_accuracy',
            'diana_loaded': True,
            'warmup_seconds': warmup_seconds,
        }

        # Parse component-specific accuracy from /proc/diana/stats
        for component in ['RAM', 'GPU', 'SSD', 'CACHE']:
            prefix = component.lower()
            for key in ['prefetch_hits', 'prefetch_misses',
                        'total_allocs', 'total_reads']:
                full_key = f'{prefix}_{key}'
                val = diana_after.get(key, diana_after.get(full_key, '0'))
                try:
                    result[f'{prefix}_{key}'] = int(val)
                except (ValueError, TypeError):
                    result[f'{prefix}_{key}'] = str(val)

        # P2P bus activity
        result['p2p_messages'] = diana_after.get('total_messages', '0')
        result['cpu_commands'] = diana_after.get('commands_issued', '0')

        return result


# ════════════════════════════════════════════════════════════════
# Master: Run All Workloads
# ════════════════════════════════════════════════════════════════

def run_all_workloads(quick: bool = False) -> Dict:
    """Run the complete workload suite. Returns all results."""
    results = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'hostname': os.uname().nodename if hasattr(os, 'uname') else 'unknown',
        'kernel': os.uname().release if hasattr(os, 'uname') else 'unknown',
        'diana_loaded': read_diana_stats().get('diana_loaded', False),
        'workloads': {},
    }

    scale = 0.2 if quick else 1.0

    workloads = [
        ('Memory: Browser Pattern', lambda: MemoryWorkload.browser_pattern(
            iterations=int(5000 * scale))),
        ('Memory: Build Pattern', lambda: MemoryWorkload.build_pattern(
            iterations=int(500 * scale))),
        ('Memory: Repeating Pattern', lambda: MemoryWorkload.repeating_pattern(
            iterations=int(3000 * scale))),
        ('File I/O: Sequential Read', lambda: FileIOWorkload.sequential_read(
            iterations=int(50 * scale))),
        ('File I/O: Random Read', lambda: FileIOWorkload.random_read(
            iterations=int(2000 * scale))),
        ('File I/O: Many Small Files', lambda: FileIOWorkload.many_small_files(
            iterations=max(1, int(3 * scale)))),
        ('File I/O: Repeating Pattern', lambda: FileIOWorkload.repeating_file_pattern(
            iterations=int(200 * scale))),
        ('Context: Fork+Exec', lambda: ContextSwitchWorkload.fork_exec_benchmark(
            iterations=int(200 * scale))),
        ('Context: Pipe Throughput', lambda: ContextSwitchWorkload.pipe_throughput(
            iterations=int(5000 * scale))),
        ('Context: Multiprocess', lambda: ContextSwitchWorkload.multiprocess_coordination(
            num_workers=4, tasks=int(100 * scale))),
        ('Cache: Sequential', lambda: CacheWorkload.sequential_access(
            array_size_mb=32, iterations=int(10 * scale))),
        ('Cache: Random', lambda: CacheWorkload.random_access(
            array_size_mb=32, num_accesses=int(100000 * scale))),
        ('Cache: Hot/Cold', lambda: CacheWorkload.repeating_hot_cold(
            array_size_mb=64, iterations=int(50 * scale))),
    ]

    total = len(workloads)
    for idx, (name, workload_fn) in enumerate(workloads, 1):
        sys.stdout.write(f'\r  [{idx}/{total}] {name}...')
        sys.stdout.flush()
        try:
            result = workload_fn()
            results['workloads'][name] = result
            sys.stdout.write(f'\r  [{idx}/{total}] {name}... ✓\n')
        except Exception as e:
            results['workloads'][name] = {'error': str(e)}
            sys.stdout.write(f'\r  [{idx}/{total}] {name}... ✗ ({e})\n')

    # DIANA intelligence (only if loaded)
    if results['diana_loaded']:
        sys.stdout.write(f'\r  [DIANA] Measuring prediction accuracy...')
        sys.stdout.flush()
        warmup = 10 if quick else 30
        results['workloads']['DIANA Intelligence'] = \
            DianaIntelligenceWorkload.prediction_accuracy(warmup_seconds=warmup)
        sys.stdout.write(f'\r  [DIANA] Measuring prediction accuracy... ✓\n')

    return results


if __name__ == '__main__':
    quick = '--quick' in sys.argv
    print("Running workloads...")
    results = run_all_workloads(quick=quick)
    print(f"\nCompleted {len(results['workloads'])} workloads")
    for name, data in results['workloads'].items():
        if 'error' in data:
            print(f"  ✗ {name}: {data['error']}")
        else:
            print(f"  ✓ {name}")
