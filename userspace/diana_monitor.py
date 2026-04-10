#!/usr/bin/env python3
"""
DIANA-OS — System Activity Monitor

Real-time system activity monitor. Watches actual user activity
and feeds events to both the LSTM brains and kernel hints.

Monitors:
  - Running applications (psutil)
  - File activity (/proc/PID/fd)
  - Memory usage patterns (/proc/meminfo)
  - CPU usage per process (/proc/stat)
  - Time of day / day type
  - Disk I/O patterns (/proc/diskstats)

Author: Sahidh — DIANA Architecture
"""

import os
import sys
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'


class DIANAMonitor:
    """
    Real system activity monitor for DIANA-OS userspace.
    Tracks actual user activity and feeds to kernel SYNAPSE.
    """

    def __init__(self, proc_path: str = "/proc/diana",
                 interval: float = 2.0):
        self.proc_path = proc_path
        self.interval = interval
        self.running = False

        # Activity tracking
        self.app_history: List[str] = []
        self.file_history: List[str] = []
        self.app_frequency: Dict[str, int] = defaultdict(int)
        self.app_transitions: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self.last_app: str = ""

        # Setup logging
        self.logger = logging.getLogger('DIANA-Monitor')
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter(LOG_FORMAT))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def get_running_apps(self) -> List[Dict]:
        """Get currently running applications with resource usage."""
        apps = []

        if not PSUTIL_AVAILABLE:
            return apps

        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent',
                                              'memory_percent', 'status']):
                try:
                    info = proc.info
                    if info['cpu_percent'] is not None and \
                       info['cpu_percent'] > 0.1:
                        apps.append({
                            'pid': info['pid'],
                            'name': info['name'],
                            'cpu': info['cpu_percent'],
                            'memory': info['memory_percent'],
                            'status': info['status'],
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Sort by CPU usage
            apps.sort(key=lambda x: x['cpu'], reverse=True)
        except Exception as e:
            self.logger.debug(f"Error getting apps: {e}")

        return apps[:20]  # Top 20

    def get_file_activity(self) -> List[Dict]:
        """Get recently accessed files via /proc/PID/fd."""
        files = []

        if not PSUTIL_AVAILABLE:
            return files

        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    open_files = proc.open_files()
                    for f in open_files[:5]:  # Limit per process
                        files.append({
                            'path': f.path,
                            'pid': proc.info['pid'],
                            'process': proc.info['name'],
                            'mode': f.mode if hasattr(f, 'mode') else 'r',
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied,
                        PermissionError):
                    continue
        except Exception as e:
            self.logger.debug(f"Error getting files: {e}")

        return files[:50]  # Top 50

    def get_memory_patterns(self) -> Dict:
        """Get system memory usage patterns."""
        if not PSUTIL_AVAILABLE:
            return {}

        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()

            return {
                'total': mem.total,
                'available': mem.available,
                'percent': mem.percent,
                'used': mem.used,
                'cached': getattr(mem, 'cached', 0),
                'buffers': getattr(mem, 'buffers', 0),
                'swap_percent': swap.percent,
                'swap_used': swap.used,
                'pressure': 'HIGH' if mem.percent > 85
                            else 'MED' if mem.percent > 60
                            else 'LOW',
            }
        except Exception:
            return {}

    def get_io_patterns(self) -> Dict:
        """Get disk I/O patterns."""
        if not PSUTIL_AVAILABLE:
            return {}

        try:
            io = psutil.disk_io_counters()
            if io:
                return {
                    'read_count': io.read_count,
                    'write_count': io.write_count,
                    'read_bytes': io.read_bytes,
                    'write_bytes': io.write_bytes,
                    'read_time': io.read_time,
                    'write_time': io.write_time,
                }
        except Exception:
            pass

        return {}

    def get_cpu_per_process(self) -> List[Dict]:
        """Get CPU usage per process."""
        if not PSUTIL_AVAILABLE:
            return []

        try:
            procs = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                try:
                    if proc.info['cpu_percent'] and \
                       proc.info['cpu_percent'] > 0.5:
                        procs.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            procs.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
            return procs[:10]
        except Exception:
            return []

    def get_time_context(self) -> Dict:
        """Get time-of-day context."""
        now = datetime.now()
        hour = now.hour

        if 6 <= hour < 12:
            period = 'morning'
        elif 12 <= hour < 17:
            period = 'afternoon'
        elif 17 <= hour < 21:
            period = 'evening'
        else:
            period = 'night'

        return {
            'hour': hour,
            'minute': now.minute,
            'period': period,
            'weekday': now.strftime('%A'),
            'is_weekend': now.weekday() >= 5,
        }

    def detect_app_transition(self, apps: List[Dict]) -> Optional[str]:
        """Detect when user switches applications."""
        if not apps:
            return None

        current_top = apps[0]['name']

        if current_top != self.last_app and self.last_app:
            self.app_transitions[self.last_app][current_top] += 1
            self.app_history.append(current_top)
            if len(self.app_history) > 100:
                self.app_history = self.app_history[-100:]

            transition = f"{self.last_app}->{current_top}"
            self.last_app = current_top
            return transition

        self.last_app = current_top
        self.app_frequency[current_top] += 1
        return None

    def feed_to_kernel(self, event: str) -> bool:
        """
        Write an event to /proc/diana/hints.
        Format: "COMPONENT:EVENT:CONFIDENCE\n"
        """
        hints_path = os.path.join(self.proc_path, 'hints')

        try:
            with open(hints_path, 'w') as f:
                f.write(event + '\n')
            return True
        except (FileNotFoundError, PermissionError):
            return False

    def monitor_cycle(self) -> Dict:
        """Run one monitoring cycle and return collected data."""
        data = {}

        # Get running apps
        apps = self.get_running_apps()
        data['apps'] = apps
        data['top_app'] = apps[0]['name'] if apps else 'idle'

        # Detect transitions
        transition = self.detect_app_transition(apps)
        if transition:
            data['transition'] = transition
            self.logger.info(f"App transition: {transition}")

            # Feed transition to kernel
            parts = transition.split('->')
            if len(parts) == 2:
                self.feed_to_kernel(
                    f"RAM:{parts[1]}_data:850"
                )

        # Memory patterns
        data['memory'] = self.get_memory_patterns()
        if data['memory'].get('pressure') == 'HIGH':
            self.feed_to_kernel("RAM:pressure_high:900")

        # I/O patterns
        data['io'] = self.get_io_patterns()

        # Time context
        data['time'] = self.get_time_context()

        return data

    def start(self):
        """Start monitoring loop."""
        self.running = True
        self.logger.info("DIANA Monitor started")

        while self.running:
            try:
                data = self.monitor_cycle()
                self.logger.debug(
                    f"Cycle: top={data.get('top_app', 'unknown')}, "
                    f"mem={data.get('memory', {}).get('percent', 0):.1f}%"
                )
            except Exception as e:
                self.logger.error(f"Monitor error: {e}")

            time.sleep(self.interval)

    def stop(self):
        """Stop monitoring."""
        self.running = False
        self.logger.info("DIANA Monitor stopped")

    def get_summary(self) -> Dict:
        """Get monitor summary."""
        return {
            'app_history_len': len(self.app_history),
            'unique_apps': len(self.app_frequency),
            'top_apps': sorted(self.app_frequency.items(),
                              key=lambda x: x[1], reverse=True)[:10],
            'transitions_tracked': sum(
                sum(v.values())
                for v in self.app_transitions.values()
            ),
            'psutil_available': PSUTIL_AVAILABLE,
        }


if __name__ == '__main__':
    import signal

    monitor = DIANAMonitor()

    def sig_handler(signum, frame):
        monitor.stop()
        print(f"\nSummary: {monitor.get_summary()}")
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    print("╔═══════════════════════════════════════╗")
    print("║  DIANA-OS System Activity Monitor     ║")
    print("║  Press Ctrl+C to stop                 ║")
    print("╚═══════════════════════════════════════╝")
    monitor.start()
