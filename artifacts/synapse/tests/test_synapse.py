"""
SYNAPSE unit tests — verifies core pattern recognition and prediction logic.
"""

import json
import os
import tempfile
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synapse.core import SynapseChip


def test_basic_prediction():
    chip = SynapseChip(order=1)
    chip.train(["A", "B", "A", "B", "A", "B"])
    assert chip.predict(["A"]) == "B"
    assert chip.predict(["B"]) == "A"
    print("  [PASS] test_basic_prediction")


def test_higher_order():
    chip = SynapseChip(order=2)
    chip.train(["A", "B", "C", "A", "B", "D", "A", "B", "C"])
    result = chip.predict(["A", "B"])
    assert result == "C", f"Expected 'C', got '{result}'"
    print("  [PASS] test_higher_order")


def test_no_data_returns_none():
    chip = SynapseChip(order=2)
    assert chip.predict() is None
    print("  [PASS] test_no_data_returns_none")


def test_unknown_context_returns_none():
    chip = SynapseChip(order=1)
    chip.train(["A", "B", "C"])
    assert chip.predict(["Z"]) is None
    print("  [PASS] test_unknown_context_returns_none")


def test_confidence_range():
    chip = SynapseChip(order=1)
    chip.train(["A", "B", "A", "B"])
    conf = chip.confidence(["A"])
    assert 0.0 <= conf <= 1.0
    print(f"  [PASS] test_confidence_range  (confidence={conf})")


def test_full_confidence():
    chip = SynapseChip(order=1)
    chip.train(["A", "B", "A", "B", "A", "B"])
    conf = chip.confidence(["A"])
    assert conf == 1.0, f"Expected 1.0, got {conf}"
    print("  [PASS] test_full_confidence")


def test_top_k():
    chip = SynapseChip(order=1)
    chip.train(["A", "B", "A", "C", "A", "B"])
    top_k = chip.predict_top_k(k=2, history=["A"])
    tasks = [t for t, _ in top_k]
    assert "B" in tasks
    assert "C" in tasks
    print(f"  [PASS] test_top_k  (top_k={top_k})")


def test_save_load(tmp_path=None):
    if tmp_path is None:
        tmp_path = tempfile.mkdtemp()
    path = os.path.join(str(tmp_path), "chip.json")

    chip = SynapseChip(order=2)
    chip.train(["X", "Y", "Z", "X", "Y", "Z"])
    chip.save(path)

    loaded = SynapseChip.load(path)
    assert loaded.order == 2
    assert loaded.predict(["X", "Y"]) == "Z"
    print("  [PASS] test_save_load")


def test_reset():
    chip = SynapseChip(order=1)
    chip.train(["A", "B"])
    chip.reset()
    assert chip.task_log == []
    assert chip.predict() is None
    print("  [PASS] test_reset")


def test_fallback_to_lower_order():
    chip = SynapseChip(order=3)
    chip.train(["A", "B", "C", "D", "A", "B", "C", "D"])
    result = chip.predict(["B", "C"])
    assert result == "D", f"Expected 'D', got '{result}'"
    print("  [PASS] test_fallback_to_lower_order")


def test_summary():
    chip = SynapseChip(order=2)
    chip.train(["P", "Q", "R", "P", "Q", "R"])
    s = chip.summary()
    assert s["tasks_observed"] == 6
    assert set(s["unique_tasks"]) == {"P", "Q", "R"}
    print("  [PASS] test_summary")


if __name__ == "__main__":
    tests = [
        test_basic_prediction,
        test_higher_order,
        test_no_data_returns_none,
        test_unknown_context_returns_none,
        test_confidence_range,
        test_full_confidence,
        test_top_k,
        test_save_load,
        test_reset,
        test_fallback_to_lower_order,
        test_summary,
    ]

    print("\n  Running SYNAPSE tests...\n")
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {t.__name__}: {e}")
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed\n")
    if failed:
        sys.exit(1)
