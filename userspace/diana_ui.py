#!/usr/bin/env python3
"""
DIANA-OS — Terminal Dashboard (curses UI)

Real-time dashboard showing DIANA-OS status:
  - P2P Bus messages
  - CPU Observer status (commands always 0)
  - Per-component SYNAPSE statistics
  - Kernel log from /proc/diana/

Author: Sahidh — DIANA Architecture
"""

import os
import sys
import time
import curses
from typing import Dict, List, Optional


class DIANAUI:
    """
    Terminal-based dashboard for DIANA-OS.
    Uses Python curses for rich terminal UI.
    """

    # Color pairs
    COLOR_TITLE = 1
    COLOR_GOOD = 2
    COLOR_WARN = 3
    COLOR_ERROR = 4
    COLOR_P2P = 5
    COLOR_CPU = 6
    COLOR_HIGHLIGHT = 7
    COLOR_DIM = 8

    def __init__(self, proc_path: str = "/proc/diana"):
        self.proc_path = proc_path
        self.running = False
        self.cycle = 0

        # Cached data
        self.stats_data = ""
        self.p2p_data = ""
        self.cpu_data = ""
        self.hints_data = ""
        self.log_lines: List[str] = []

    def read_proc_file(self, name: str) -> str:
        """Read a /proc/diana/ file safely."""
        path = os.path.join(self.proc_path, name)
        try:
            with open(path, 'r') as f:
                return f.read()
        except (FileNotFoundError, PermissionError):
            return f"[{name} not available - is DIANA kernel module loaded?]"

    def refresh_data(self):
        """Read all proc files."""
        self.stats_data = self.read_proc_file('stats')
        self.p2p_data = self.read_proc_file('p2p_log')
        self.cpu_data = self.read_proc_file('cpu_report')
        self.hints_data = self.read_proc_file('hints')
        self.cycle += 1

    def parse_component_stats(self) -> Dict[str, Dict]:
        """Parse stats into per-component dictionaries."""
        components = {}
        current = None

        for line in self.stats_data.split('\n'):
            line = line.strip()
            if line.startswith('[') and 'SYNAPSE' in line:
                name = line.strip('[]').split()[0]
                current = name
                components[current] = {}
            elif line.startswith('[') and current:
                name = line.strip('[]').split()[0]
                current = name
                components[current] = {}
            elif ':' in line and current:
                key, _, value = line.partition(':')
                components[current][key.strip()] = value.strip()

        return components

    def draw_box(self, screen, y: int, x: int, h: int, w: int,
                 title: str = "", color_pair: int = 0):
        """Draw a bordered box with optional title."""
        try:
            # Top border
            screen.addstr(y, x, '╔' + '═' * (w - 2) + '╗', 
                         curses.color_pair(color_pair))
            # Bottom border
            screen.addstr(y + h - 1, x, '╚' + '═' * (w - 2) + '╝',
                         curses.color_pair(color_pair))
            # Sides
            for i in range(1, h - 1):
                screen.addstr(y + i, x, '║',
                             curses.color_pair(color_pair))
                screen.addstr(y + i, x + w - 1, '║',
                             curses.color_pair(color_pair))
            # Title
            if title:
                title_str = f' {title} '
                tx = x + (w - len(title_str)) // 2
                screen.addstr(y, tx, title_str,
                             curses.color_pair(self.COLOR_TITLE) |
                             curses.A_BOLD)
        except curses.error:
            pass

    def draw_component(self, screen, y: int, x: int, w: int,
                       name: str, data: Dict, color: int):
        """Draw a component status panel."""
        accuracy = data.get('accuracy', '0%')
        predictions = data.get('predictions', '0')
        patterns = data.get('patterns_learned', '0')

        try:
            screen.addstr(y, x, f"  {name}", 
                         curses.color_pair(color) | curses.A_BOLD)
            screen.addstr(y + 1, x, f"  Accuracy: {accuracy}",
                         curses.color_pair(self.COLOR_GOOD))
            screen.addstr(y + 2, x, f"  Predict: {predictions}",
                         curses.color_pair(self.COLOR_DIM))
            screen.addstr(y + 3, x, f"  Learned: {patterns}",
                         curses.color_pair(self.COLOR_DIM))
        except curses.error:
            pass

    def _draw(self, screen):
        """Main drawing function called every refresh."""
        screen.clear()
        max_y, max_x = screen.getmaxyx()

        # Refresh data
        self.refresh_data()
        components = self.parse_component_stats()

        # ── Title Bar ──
        title = "DIANA-OS — SYNAPSE Chip Intelligence"
        subtitle = "Distributed Intelligent Autonomous Neural Architecture"
        try:
            self.draw_box(screen, 0, 0, 3, min(max_x, 52), title,
                         self.COLOR_TITLE)
            screen.addstr(1, 2, subtitle[:max_x - 4],
                         curses.color_pair(self.COLOR_DIM))
        except curses.error:
            pass

        row = 3

        # ── P2P Bus + CPU Observer ──
        panel_w = min(max_x // 2, 30)

        # P2P panel
        try:
            self.draw_box(screen, row, 0, 8, panel_w, "P2P BUS",
                         self.COLOR_P2P)

            p2p_lines = self.p2p_data.strip().split('\n')
            # Show last few messages
            msg_lines = [l for l in p2p_lines 
                        if '->' in l and 'TIMESTAMP' not in l][-5:]
            for i, line in enumerate(msg_lines):
                screen.addstr(row + 1 + i, 2, line[:panel_w - 4],
                             curses.color_pair(self.COLOR_P2P))

            # Total count
            for l in p2p_lines:
                if 'Total messages' in l:
                    screen.addstr(row + 6, 2, l.strip()[:panel_w - 4],
                                 curses.color_pair(self.COLOR_HIGHLIGHT))
                    break
        except curses.error:
            pass

        # CPU Observer panel
        try:
            cpu_x = panel_w + 1
            cpu_w = min(max_x - cpu_x, 30)
            self.draw_box(screen, row, cpu_x, 8, cpu_w,
                         "CPU OBSERVER", self.COLOR_CPU)

            cpu_lines = self.cpu_data.strip().split('\n')
            for i, line in enumerate(cpu_lines[:6]):
                line = line.strip()
                color = self.COLOR_DIM
                if 'commands_issued: 0' in line:
                    color = self.COLOR_GOOD
                elif 'commands_issued' in line and '0' not in line:
                    color = self.COLOR_ERROR
                elif 'status_updates' in line:
                    color = self.COLOR_HIGHLIGHT

                screen.addstr(row + 1 + i, cpu_x + 2,
                             line[:cpu_w - 4],
                             curses.color_pair(color))
        except curses.error:
            pass

        row += 9

        # ── Component Panels ──
        comp_w = min(max_x // 4, 18)
        comp_names = ['RAM', 'GPU', 'SSD', 'CACHE']
        comp_colors = [self.COLOR_GOOD, self.COLOR_P2P,
                      self.COLOR_WARN, self.COLOR_HIGHLIGHT]

        try:
            total_w = min(max_x, comp_w * 4 + 3)
            self.draw_box(screen, row, 0, 6, total_w,
                         "SYNAPSE Components", self.COLOR_TITLE)

            for i, (name, color) in enumerate(
                    zip(comp_names, comp_colors)):
                data = components.get(name, {})
                self.draw_component(screen, row + 1,
                                   i * comp_w + 1, comp_w,
                                   name, data, color)
        except curses.error:
            pass

        row += 7

        # ── Kernel Log ──
        log_h = max(max_y - row - 1, 5)
        log_w = min(max_x, 60)

        try:
            self.draw_box(screen, row, 0, log_h, log_w,
                         "KERNEL LOG — /proc/diana/", self.COLOR_DIM)

            # Mix stats and P2P for log display
            log_entries = []
            for line in self.stats_data.split('\n'):
                line = line.strip()
                if line and not line.startswith('═') and \
                   not line.startswith('╔') and \
                   not line.startswith('╚') and \
                   not line.startswith('║'):
                    log_entries.append(line)

            for i, entry in enumerate(log_entries[-(log_h - 2):]):
                color = self.COLOR_DIM
                if '[RAM' in entry or 'RAM' in entry:
                    color = self.COLOR_GOOD
                elif '[GPU' in entry or 'GPU' in entry:
                    color = self.COLOR_P2P
                elif '[SSD' in entry or 'SSD' in entry:
                    color = self.COLOR_WARN
                elif '[CACHE' in entry or 'CACHE' in entry:
                    color = self.COLOR_HIGHLIGHT

                screen.addstr(row + 1 + i, 2,
                             entry[:log_w - 4],
                             curses.color_pair(color))
        except curses.error:
            pass

        # Status bar
        try:
            status = (f" Cycle: {self.cycle} | "
                     f"Press 'q' to quit | "
                     f"Refresh: 1s ")
            screen.addstr(max_y - 1, 0, status[:max_x - 1],
                         curses.color_pair(self.COLOR_TITLE) |
                         curses.A_REVERSE)
        except curses.error:
            pass

        screen.refresh()

    def start(self):
        """Start the curses UI."""
        curses.wrapper(self._curses_main)

    def _curses_main(self, screen):
        """Main curses loop."""
        # Setup colors
        curses.start_color()
        curses.use_default_colors()

        curses.init_pair(self.COLOR_TITLE, curses.COLOR_CYAN, -1)
        curses.init_pair(self.COLOR_GOOD, curses.COLOR_GREEN, -1)
        curses.init_pair(self.COLOR_WARN, curses.COLOR_YELLOW, -1)
        curses.init_pair(self.COLOR_ERROR, curses.COLOR_RED, -1)
        curses.init_pair(self.COLOR_P2P, curses.COLOR_BLUE, -1)
        curses.init_pair(self.COLOR_CPU, curses.COLOR_MAGENTA, -1)
        curses.init_pair(self.COLOR_HIGHLIGHT, curses.COLOR_WHITE, -1)
        curses.init_pair(self.COLOR_DIM, 8, -1)  # Bright black = gray

        curses.curs_set(0)  # Hide cursor
        screen.timeout(1000)  # 1 second refresh

        self.running = True

        while self.running:
            try:
                self._draw(screen)
            except Exception:
                pass

            # Check for quit key
            try:
                key = screen.getch()
                if key == ord('q') or key == ord('Q') or key == 27:
                    self.running = False
            except Exception:
                pass


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='DIANA-OS Terminal Dashboard'
    )
    parser.add_argument('--proc-path', default='/proc/diana',
                       help='Path to DIANA proc interface')
    args = parser.parse_args()

    print("╔═══════════════════════════════════════╗")
    print("║  DIANA-OS Terminal Dashboard          ║")
    print("║  Loading...                           ║")
    print("╚═══════════════════════════════════════╝")

    ui = DIANAUI(proc_path=args.proc_path)
    ui.start()


if __name__ == '__main__':
    main()
