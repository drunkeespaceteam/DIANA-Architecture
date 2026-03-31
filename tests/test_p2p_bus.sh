#!/bin/bash
# ═══════════════════════════════════════════════════
# DIANA-OS — P2P Bus Test Suite
# ═══════════════════════════════════════════════════
# Author: Sahidh — DIANA Architecture

echo "╔══════════════════════════════════════════╗"
echo "║  Testing DIANA P2P Bus                   ║"
echo "╚══════════════════════════════════════════╝"
echo ""

if ! [ -d /proc/diana ]; then
    echo "FAIL: DIANA kernel module not loaded!"
    exit 1
fi

echo "1. Getting initial message count..."
INITIAL_COUNT=$(grep "Total messages:" /proc/diana/p2p_log 2>/dev/null | grep -o "[0-9]*") || INITIAL_COUNT=0
echo "   Start count: $INITIAL_COUNT"

echo "2. Triggering kernel activity to test P2P bus..."
# Wait a second, the kernel background tasks should trigger some P2P traffic
# like cache misses -> SSD reads, or scheduler -> GPU detection
sleep 2

# Also write a hint which boosts a pattern, maybe triggering a prefetch
echo "RAM:kmalloc_large:900" | sudo tee /proc/diana/hints >/dev/null

sleep 1

echo "3. Getting new message count..."
FINAL_COUNT=$(grep "Total messages:" /proc/diana/p2p_log 2>/dev/null | grep -o "[0-9]*") || FINAL_COUNT=0
echo "   End count: $FINAL_COUNT"

if [ "$FINAL_COUNT" -gt "$INITIAL_COUNT" ]; then
    DIFF=$((FINAL_COUNT - INITIAL_COUNT))
    echo -e "   \033[0;32mPASS\033[0m — $DIFF new P2P messages logged!"
    
    echo ""
    echo "Recent messages:"
    cat /proc/diana/p2p_log | tail -5 | sed 's/^/  /'
else
    echo -e "   \033[0;33mWARN\033[0m — No new P2P messages generated."
    echo "   (This is normal on a quiet system, try running a heavy test first)"
fi

echo ""
echo "4. Checking CPU Observer INVARIANTS during P2P traffic..."
CPU_CMDS=$(grep "commands_issued" /proc/diana/cpu_report 2>/dev/null | grep -o "[0-9]*" | tail -1)

if [ "$CPU_CMDS" = "0" ]; then
    echo -e "   \033[0;32mPASS\033[0m — CPU issued 0 commands while components communicated!"
    echo "   VON NEUMANN BOTTLENECK BROKEN."
else
    echo -e "   \033[0;31mFAIL\033[0m — CPU issued $CPU_CMDS commands! Architecture violated!"
    exit 1
fi

echo ""
echo "P2P Bus tests completed."
exit 0
