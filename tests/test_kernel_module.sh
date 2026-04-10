#!/bin/bash
# ═══════════════════════════════════════════════════
# DIANA-OS — Kernel Module Test Suite
# ═══════════════════════════════════════════════════
# Author: Sahidh — DIANA Architecture

echo "╔══════════════════════════════════════════╗"
echo "║  Testing DIANA Kernel Module             ║"
echo "╚══════════════════════════════════════════╝"
echo ""

PASS=0
FAIL=0

# Helper function
check() {
    local name="$1"
    local result="$2"
    echo -n "Test $name: "
    if [ "$result" = "0" ]; then
        echo -e "\033[0;32mPASS\033[0m"
        PASS=$((PASS+1))
    else
        echo -e "\033[0;31mFAIL\033[0m"
        FAIL=$((FAIL+1))
    fi
}

# ── Test 1: Module loads ──
RES=1
if lsmod 2>/dev/null | grep -q diana_core; then
    RES=0
else
    # Try loading it
    sudo insmod kernel/diana_core.ko 2>/dev/null || true
    if lsmod 2>/dev/null | grep -q diana_core; then
        RES=0
    fi
fi
check "1 (Module loads)" $RES

# Fast-fail if no module
if [ $RES -ne 0 ]; then
    echo ""
    echo "Module not loaded — cannot continue kernel tests."
    echo "Build first: make module"
    exit 1
fi

# ── Test 2: /proc/diana exists ──
RES=1
[ -d /proc/diana ] && RES=0
check "2 (/proc/diana created)" $RES

# ── Test 3: Stats readable ──
RES=1
cat /proc/diana/stats >/dev/null 2>&1 && RES=0
check "3 (Stats readable)" $RES

# ── Test 4: CPU commands always zero ──
RES=1
CMDS=$(grep "commands_issued" /proc/diana/cpu_report 2>/dev/null | grep -o "[0-9]*" | tail -1)
if [ "$CMDS" = "0" ]; then
    RES=0
else
    echo "  -> CRITICAL FAILURE: CPU commands_issued = $CMDS (MUST BE 0)"
fi
check "4 (CPU commands zero)" $RES

# ── Test 5: P2P log accessible ──
RES=1
cat /proc/diana/p2p_log >/dev/null 2>&1 && RES=0
check "5 (P2P log accessible)" $RES

# ── Test 6: Hints writable ──
RES=1
# Format: COMPONENT:EVENT:CONFIDENCE
echo "RAM:browser_data:890" | sudo tee /proc/diana/hints >/dev/null 2>&1 && RES=0
check "6 (Hints writable)" $RES

# ── Test 7: Hints processed ──
RES=1
LAST_HINT=$(cat /proc/diana/hints 2>/dev/null | grep -v "===" | grep -A 1 "Last hint" | tail -1 | xargs)
if [ "$LAST_HINT" = "RAM:browser_data:890" ]; then
    RES=0
else
    echo "  -> Expected RAM:browser_data:890, got: $LAST_HINT"
fi
check "7 (Hints processed correctly)" $RES

echo ""
echo "=== Results ==="
echo "Passed: $PASS"
echo "Failed: $FAIL"

if [ $FAIL -gt 0 ]; then
    exit 1
fi
exit 0
