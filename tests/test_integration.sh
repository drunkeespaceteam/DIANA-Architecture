#!/bin/bash
# ═══════════════════════════════════════════════════
# DIANA-OS — Full Integration Test
# ═══════════════════════════════════════════════════
# Author: Sahidh — DIANA Architecture

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "╔══════════════════════════════════════════╗"
echo "║  Full DIANA-OS Integration Test          ║"
echo "╚══════════════════════════════════════════╝"
echo ""

if ! [ -d /proc/diana ]; then
    echo "FAIL: DIANA kernel module not loaded!"
    exit 1
fi

echo "[1/4] Starting trainer in test mode..."
python3 "$PROJECT_DIR/userspace/diana_trainer.py" --test-mode > /tmp/diana_test.log 2>&1 &
TRAINER_PID=$!

echo "Waiting for trainer to complete cycles (10s)..."
for i in {1..10}; do
    echo -n "."
    sleep 1
done
echo ""

# Make sure it's dead
kill $TRAINER_PID 2>/dev/null || true

echo ""
echo "[2/4] Checking kernel stats updated by LSTM..."
STATS=$(cat /proc/diana/stats 2>/dev/null)
if echo "$STATS" | grep -q "predictions"; then
    echo -e "  \033[0;32mPASS\033[0m — predictions made"
else
    echo -e "  \033[0;31mFAIL\033[0m — no predictions in stats"
fi

echo ""
echo "[3/4] Checking P2P messages flowing..."
MSG_COUNT=$(cat /proc/diana/p2p_log 2>/dev/null | grep -c "->") || true
if [ "$MSG_COUNT" -gt 0 ]; then
    echo -e "  \033[0;32mPASS\033[0m — $MSG_COUNT P2P messages delivered"
else
    echo -e "  \033[0;31mFAIL\033[0m — no P2P messages"
fi

echo ""
echo "[4/4] Checking CPU commands still zero..."
CPU_CMDS=$(grep "commands_issued" /proc/diana/cpu_report 2>/dev/null | grep -o "[0-9]*" | tail -1)
if [ "$CPU_CMDS" = "0" ]; then
    echo -e "  \033[0;32mPASS\033[0m — CPU issued 0 commands! Architecture Validated."
else
    echo -e "  \033[0;31mCRITICAL FAIL\033[0m — CPU issued $CPU_CMDS commands!"
    exit 1
fi

echo ""
echo "=== Integration Test Complete ==="
exit 0
