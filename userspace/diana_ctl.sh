#!/bin/bash
# DIANA-OS Control Script
# Manage DIANA services: start, stop, status, reload
#
# Author: Sahidh — DIANA Architecture

set -e

DIANA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROC_PATH="/proc/diana"
MODEL_DIR="/var/lib/diana/models"
PID_FILE="/var/run/diana_trainer.pid"
LOG_FILE="/var/log/diana_trainer.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

banner() {
    echo -e "${CYAN}╔═══════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  DIANA-OS Control — v0.1              ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════╝${NC}"
}

status_kernel() {
    echo -e "${CYAN}=== Kernel Module ===${NC}"
    if lsmod 2>/dev/null | grep -q diana_core; then
        echo -e "  Module: ${GREEN}LOADED${NC}"
    else
        echo -e "  Module: ${RED}NOT LOADED${NC}"
        return
    fi

    if [ -d "$PROC_PATH" ]; then
        echo -e "  /proc/diana: ${GREEN}EXISTS${NC}"
        echo ""
        echo -e "${CYAN}=== Component Stats ===${NC}"
        cat "$PROC_PATH/stats" 2>/dev/null || echo "  (cannot read stats)"
        echo ""
        echo -e "${CYAN}=== CPU Observer ===${NC}"
        cat "$PROC_PATH/cpu_report" 2>/dev/null || echo "  (cannot read)"
        echo ""
        echo -e "${CYAN}=== P2P Bus (last 10) ===${NC}"
        cat "$PROC_PATH/p2p_log" 2>/dev/null | tail -10 || echo "  (empty)"
    else
        echo -e "  /proc/diana: ${RED}MISSING${NC}"
    fi
}

status_trainer() {
    echo ""
    echo -e "${CYAN}=== DIANA Trainer ===${NC}"
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo -e "  Trainer: ${GREEN}RUNNING${NC} (PID: $PID)"
        else
            echo -e "  Trainer: ${RED}STALE PID${NC} ($PID)"
        fi
    else
        echo -e "  Trainer: ${YELLOW}NOT RUNNING${NC}"
    fi

    if [ -d "$MODEL_DIR" ]; then
        echo -e "  Models: ${GREEN}$(ls $MODEL_DIR 2>/dev/null | wc -l) files${NC}"
    fi
}

cmd_start() {
    banner
    echo ""

    # Load kernel module if not loaded
    if ! lsmod 2>/dev/null | grep -q diana_core; then
        echo "Loading DIANA kernel module..."
        if [ -f "$DIANA_DIR/kernel/diana_core.ko" ]; then
            sudo insmod "$DIANA_DIR/kernel/diana_core.ko" || {
                echo -e "${RED}Failed to load kernel module${NC}"
                echo "Build first: cd $DIANA_DIR && make module"
            }
        else
            echo -e "${YELLOW}Kernel module not built.${NC}"
            echo "Run: cd $DIANA_DIR && make module"
        fi
    fi

    # Start trainer daemon
    echo "Starting DIANA trainer daemon..."
    python3 "$DIANA_DIR/userspace/diana_trainer.py" --daemon \
        --proc-path "$PROC_PATH" \
        --model-dir "$MODEL_DIR" || {
        echo -e "${YELLOW}Trainer started in foreground mode${NC}"
    }

    echo ""
    echo -e "${GREEN}DIANA-OS services started!${NC}"
    echo "  Dashboard: python3 $DIANA_DIR/userspace/diana_ui.py"
    echo "  Status:    $0 status"
}

cmd_stop() {
    banner
    echo ""

    # Stop trainer
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping trainer (PID: $PID)..."
            kill "$PID"
            rm -f "$PID_FILE"
            echo -e "${GREEN}Trainer stopped${NC}"
        fi
    fi

    # Unload kernel module
    if lsmod 2>/dev/null | grep -q diana_core; then
        echo "Unloading DIANA kernel module..."
        sudo rmmod diana_core || echo -e "${RED}Failed to unload${NC}"
        echo -e "${GREEN}Kernel module unloaded${NC}"
    fi

    echo -e "${GREEN}DIANA-OS services stopped${NC}"
}

cmd_reload() {
    echo "Reloading DIANA-OS..."
    cmd_stop
    sleep 1
    cmd_start
}

cmd_status() {
    banner
    echo ""
    status_kernel
    status_trainer
}

cmd_dashboard() {
    python3 "$DIANA_DIR/userspace/diana_ui.py" --proc-path "$PROC_PATH"
}

cmd_monitor() {
    python3 "$DIANA_DIR/userspace/diana_monitor.py"
}

cmd_logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo "No log file found at $LOG_FILE"
        echo "Try: journalctl -f | grep diana"
    fi
}

# Main
case "${1:-help}" in
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart|reload)
        cmd_reload
        ;;
    status)
        cmd_status
        ;;
    dashboard|ui)
        cmd_dashboard
        ;;
    monitor)
        cmd_monitor
        ;;
    logs)
        cmd_logs
        ;;
    help|*)
        banner
        echo ""
        echo "Usage: $0 {start|stop|restart|status|dashboard|monitor|logs}"
        echo ""
        echo "Commands:"
        echo "  start      Load kernel module + start trainer daemon"
        echo "  stop       Stop trainer + unload kernel module"
        echo "  restart    Stop then start"
        echo "  status     Show all DIANA component status"
        echo "  dashboard  Launch terminal UI"
        echo "  monitor    Launch system activity monitor"
        echo "  logs       Tail trainer log file"
        ;;
esac
