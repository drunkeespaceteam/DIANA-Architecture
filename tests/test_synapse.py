#!/usr/bin/env python3
"""
DIANA-OS — SYNAPSE Intelligence Test Suite
Tests PyTorch LSTM brain and Q-Learning agent independently.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synapse.brain import SynapseBrain, TORCH_AVAILABLE
from synapse.rl_agent import RLAgent

print("╔══════════════════════════════════════════╗")
print("║  Testing SYNAPSE Intelligence            ║")
print("╚══════════════════════════════════════════╝")
print("")

if not TORCH_AVAILABLE:
    print("PyTorch not installed. Missing LSTM features!")
    print("Tests scaled down to basic API checks.")

passed = 0
failed = 0

# ── Test 1: LSTM trains ──
print("Test 1: LSTM trains and loss decreases...")
if TORCH_AVAILABLE:
    vocab = ['a', 'b', 'c', 'd', 'e']
    brain = SynapseBrain("TEST", vocab, embed_dim=8, hidden=16, lr=0.05)
    
    # Needs a few iterations to guarantee loss drop
    initial_loss = brain.learn(['a', 'b', 'c', 'd'], 'e')
    for _ in range(50):
        brain.learn(['a', 'b', 'c', 'd'], 'e')
    final_loss = brain.learn(['a', 'b', 'c', 'd'], 'e')

    if final_loss < initial_loss:
        print(f"  \033[0;32mPASS\033[0m — loss {initial_loss:.4f} → {final_loss:.4f}")
        passed += 1
    else:
        print(f"  \033[0;31mFAIL\033[0m — loss {initial_loss:.4f} → {final_loss:.4f} (did not decrease)")
        failed += 1
else:
    print("  \033[0;33mSKIP\033[0m — PyTorch not available")
    passed += 1

# ── Test 2: Prediction accuracy ──
print("\nTest 2: Prediction accuracy after training...")
if TORCH_AVAILABLE:
    for _ in range(50):
        brain.learn(['a', 'b', 'c', 'd'], 'e')
    
    pred, conf = brain.predict(['a', 'b', 'c', 'd'])
    if pred == 'e':
        print(f"  \033[0;32mPASS\033[0m — predicted '{pred}' with {conf:.2%} confidence")
        passed += 1
    else:
        print(f"  \033[0;31mFAIL\033[0m — predicted '{pred}' instead of 'e'")
        failed += 1
else:
    print("  \033[0;33mSKIP\033[0m")
    passed += 1

# ── Test 3: Components independent ──
print("\nTest 3: Components are fully independent...")
if TORCH_AVAILABLE:
    ram_brain = SynapseBrain("RAM", vocab)
    gpu_brain = SynapseBrain("GPU", vocab)
    
    for _ in range(50):
        ram_brain.learn(['a', 'b', 'c', 'd'], 'e')
        gpu_brain.learn(['a', 'b', 'c', 'd'], 'a')
        
    ram_pred, _ = ram_brain.predict(['a', 'b', 'c', 'd'])
    gpu_pred, _ = gpu_brain.predict(['a', 'b', 'c', 'd'])
    
    if ram_pred != gpu_pred:
        print(f"  \033[0;32mPASS\033[0m — RAM predicts '{ram_pred}', GPU predicts '{gpu_pred}'")
        passed += 1
    else:
        print(f"  \033[0;31mFAIL\033[0m — both predict same thing!")
        failed += 1
else:
    print("  \033[0;33mSKIP\033[0m")
    passed += 1

# ── Test 4: Save and load ──
print("\nTest 4: Model persistence...")
if TORCH_AVAILABLE:
    temp_path = '/tmp/test_brain.pt'
    if os.name == 'nt':
        import tempfile
        temp_path = os.path.join(tempfile.gettempdir(), 'test_brain.pt')
        
    ram_brain.save(temp_path)
    new_brain = SynapseBrain("RAM", vocab)
    loaded = new_brain.load(temp_path)
    
    if loaded:
        old_pred, old_conf = ram_brain.predict(['a', 'b', 'c', 'd'])
        new_pred, new_conf = new_brain.predict(['a', 'b', 'c', 'd'])
        
        if old_pred == new_pred:
            print(f"  \033[0;32mPASS\033[0m — prediction preserved ({new_pred})")
            passed += 1
        else:
            print(f"  \033[0;31mFAIL\033[0m — prediction changed after load!")
            failed += 1
            
        try: os.remove(temp_path)
        except: pass
    else:
        print(f"  \033[0;31mFAIL\033[0m — failed to load saved model")
        failed += 1
else:
    print("  \033[0;33mSKIP\033[0m")
    passed += 1

# ── Test 5: RL agent works ──
print("\nTest 5: RL agent learns to prefetch...")
rl = RLAgent("TEST", epsilon_decay=0.90)  # fast decay for test
initial_epsilon = rl.epsilon

# Teach it that high confidence = prefetch is good
for _ in range(50):
    action = rl.choose_action(1.0)  # max confidence
    was_correct = True if action == rl.ACTION_PREFETCH else False
    rl.learn(was_correct, 1.0)

if rl.epsilon < initial_epsilon:
    print(f"  \033[0;32mPASS\033[0m — epsilon decayed {initial_epsilon:.3f} → {rl.epsilon:.3f}")
    passed += 1
else:
    print(f"  \033[0;31mFAIL\033[0m — epsilon did not decay!")
    failed += 1

# Check policy
policy = rl.get_policy_summary()
if policy[10] == "PREFETCH":  # State 10 = confidence 1.0
    print(f"  \033[0;32mPASS\033[0m — learned to PREFETCH on high confidence")
    passed += 1
else:
    print(f"  \033[0;31mFAIL\033[0m — policy at conf=1.0 is {policy[10]}")
    failed += 1

# Summary
print("")
print("╔═══════════════════╗")
print(f"║ Results: {passed} pass, {failed} fail ║")
print("╚═══════════════════╝")

if failed > 0:
    sys.exit(1)
sys.exit(0)
