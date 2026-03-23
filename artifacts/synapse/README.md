# SYNAPSE

> Intelligent chip that watches tasks, learns patterns, and predicts the next task.

SYNAPSE uses **n-gram pattern recognition** (a Markov chain approach) to learn which tasks tend to follow others and then predicts what comes next with a confidence score.

---

## Quick Start

```bash
# Run DIANA Phase 2 — P2P architecture simulation
python main.py --diana
```

```bash
# Interactive REPL — type tasks one by one
python main.py

# Train on a comma-separated list and predict
python main.py --tasks "wake_up,shower,breakfast,commute,work,lunch,work,commute,dinner"

# Train from a file (one task per line)
python main.py --file tasks.txt

# Run the built-in demo
python main.py --demo

# Adjust the context window (default 2)
python main.py --order 3 --tasks "A,B,C,A,B,C,A,B"
```

---

## How It Works

SYNAPSE maintains an **n-gram frequency table**: for every observed context window of *n* tasks it records how often each task followed. When asked for a prediction it:

1. Looks up the most recent *n* tasks as the context
2. Returns the most frequently observed follower
3. Falls back to shorter contexts if the full context hasn't been seen before
4. Reports a confidence score (0–100%) based on how dominant the top prediction is

### Example

```
Tasks observed: wake_up → brush_teeth → shower → breakfast → commute → work
                wake_up → brush_teeth → shower → breakfast → commute → work
                wake_up → gym        → shower → breakfast → commute → work

Context: [wake_up, brush_teeth]  →  Prediction: shower   (100%)
Context: [wake_up, gym]          →  Prediction: shower   (100%)
Context: [shower, breakfast]     →  Prediction: commute  (100%)
```

---

## Running Tests

```bash
python tests/test_synapse.py
```

---

## Project Structure

```
synapse/
├── main.py              # CLI entry point
├── synapse/
│   ├── __init__.py      # Public API
│   ├── core.py          # SynapseChip — pattern learning & prediction
│   ├── display.py       # Console formatting helpers
│   └── repl.py          # Interactive REPL
└── tests/
    └── test_synapse.py  # Unit tests
```

---

## API Reference

```python
from synapse import SynapseChip

chip = SynapseChip(order=2)   # 2-gram context window

chip.train(["A", "B", "C", "A", "B", "C"])   # batch training
chip.observe("A")                              # single-step observation

chip.predict()                                 # → "B"
chip.confidence()                              # → 1.0
chip.predict_top_k(k=3)                        # → [("B", 4), ...]

chip.save("chip.json")                         # persist to disk
chip2 = SynapseChip.load("chip.json")          # restore
chip.reset()                                   # clear memory
chip.summary()                                 # introspect
```
